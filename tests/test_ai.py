import json

import anthropic
import httpx2
import pytest

from dropkit.ai import AIError, ListingWriter, Researcher, clean_title, sanitize_html
from dropkit.models import SupplierProduct


def _client(handler):
    return anthropic.Anthropic(api_key="test", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))


def _sse(message):
    """Encode a full Message as an SSE stream the SDK can consume."""
    events = [("message_start", {"type": "message_start", "message": {**message, "content": [], "stop_reason": None}})]
    for i, block in enumerate(message["content"]):
        if block["type"] == "text":
            events.append(("content_block_start", {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}}))
            events.append(("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": block["text"]}}))
            events.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    events.append(("message_delta", {"type": "message_delta", "delta": {"stop_reason": message["stop_reason"], "stop_sequence": None}, "usage": {"output_tokens": 10}}))
    events.append(("message_stop", {"type": "message_stop"}))
    body = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return httpx2.Response(200, text=body, headers={"content-type": "text/event-stream"})


def _message(payload, stop="end_turn", content=None):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content if content is not None else [{"type": "text", "text": json.dumps(payload)}],
        "stop_reason": stop, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10},
    }


PRODUCT = SupplierProduct(supplier="aliexpress", url="u", title="2024 New Magnetic Car Holder", price=4.5,
                          attributes={"Material": "ABS", "sku_attr": "14:1"})


def test_sanitize_html():
    dirty = '<div style="x"><h3 class="a">Hi</h3><p onclick="e()">A &amp; B<script>alert(1)</script></p><a href="http://x">link</a><img src="x"><ul><li>One</li></ul></div>'
    clean = sanitize_html(dirty)
    assert clean == "<h3>Hi</h3><p>A &amp; B</p>link<ul><li>One</li></ul>"


def test_clean_title():
    assert clean_title("Super!! Phone *Holder* ~ NEW") == "Super Phone Holder NEW"
    long = "Magnetic Car Phone Mount " * 6
    out = clean_title(long)
    assert len(out) <= 80 and not out.endswith(" ")


def test_listing_writer_request_and_cleanup():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        seen["beta"] = req.headers.get("anthropic-beta")
        return httpx2.Response(200, json=_message({
            "title": "Magnetic Car Phone Mount Dashboard Holder 360 Rotation Strong Magnet for All Phones Extra Words",
            "description_html": "<p>Strong magnet<script>x</script></p>",
            "item_specifics": [{"name": "Brand", "value": "Unbranded"}],
            "search_keywords": ["magnetic car phone mount"],
            "condition": "NEW",
        }))

    out = ListingWriter(_client(handler), model="claude-opus-5-5").write(PRODUCT, "EBAY_FR")
    assert len(out.title) <= 80
    assert out.description_html == "<p>Strong magnet</p>"
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default" and seen["beta"] == "server-side-fallback-2026-07-01"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "French (France)" in body["messages"][0]["content"]
    assert "sku_attr" not in body["messages"][0]["content"]
    assert "temperature" not in body and "thinking" not in body


def test_listing_writer_refusal():
    handler = lambda req: httpx2.Response(200, json=_message(None, stop="refusal", content=[]))
    with pytest.raises(AIError):
        ListingWriter(_client(handler)).write(PRODUCT)


def test_listing_writer_api_error():
    handler = lambda req: httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "bad"}})
    with pytest.raises(AIError, match="400"):
        ListingWriter(_client(handler)).write(PRODUCT)


def test_researcher_handles_pause_turn():
    calls = []
    report = {"marketplace": "EBAY_US", "niche": "gaming", "notes": "", "ideas": [{
        "name": "Switch 2 case", "why_it_sells": "launch demand", "target_sale_price": 19.99, "est_supplier_cost": 5.0,
        "est_margin_pct": 30, "vero_risk": "medium", "verify_search": "switch 2 case", "supplier_search": "switch 2 hard case",
        "sources": ["https://example.com"]}]}

    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        if len(calls) == 1:
            return _sse(_message(None, stop="pause_turn", content=[{"type": "text", "text": "searching"}]))
        return _sse(_message(report))

    out = Researcher(_client(handler)).run("EBAY_US", "gaming", 1, exclude=["Old item"])
    assert out.ideas[0].name == "Switch 2 case"
    assert len(calls) == 2 and calls[1]["messages"][1]["role"] == "assistant"
    assert calls[0]["tools"][0]["type"] == "web_search_20260209" and calls[0]["stream"] is True
    assert "Old item" in calls[0]["messages"][0]["content"]
