"""Claude-powered listing copy and product research."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

import anthropic

from .models import ListingContent, ResearchReport, SupplierProduct

FALLBACK_BETA = "server-side-fallback-2026-07-01"

LOCALES = {
    "EBAY_US": ("English (United States)", "USD"),
    "EBAY_GB": ("English (United Kingdom)", "GBP"),
    "EBAY_FR": ("French (France)", "EUR"),
    "EBAY_DE": ("German (Germany)", "EUR"),
}

LISTING_SYSTEM = """You write eBay listings that sell and stay compliant.

Title rules:
- At most 80 characters. Front-load the words buyers actually search for.
- No ALL CAPS words, no emojis, no symbols like ! * ~, no "L@@K", no shipping or price claims.
- Never present an unbranded item as a branded one. If it fits a branded device, write "for <Device>" or "Compatible with <Device>" and never use words like genuine, original, official, OEM or authentic.
- Do not mention the supplier, AliExpress, Amazon, dropshipping, or delivery times.

Description rules:
- Simple HTML only: <h3>, <p>, <ul>, <li>, <strong>, <br>. No styles, scripts, links, images or external references.
- Lead with what the buyer gets and the problem it solves, then a feature list, then "What's in the box" and dimensions/compatibility when known.
- Only state facts present in the supplier data. Do not invent certifications, warranties, materials or measurements.

Item specifics: give eBay-style name/value pairs (Brand=Unbranded unless a real brand is sold, Type, Color, Material, Compatible Model, MPN=Does Not Apply when unknown).
Write everything in the requested language."""

RESEARCH_SYSTEM = """You are a product researcher for a small eBay seller who sources from AliExpress (US warehouses preferred) or wholesalers.
Use web search to find products that are selling fast right now on the requested eBay marketplace: recent trend reports, eBay trending searches, sold-listing data cited by tools such as Terapeak/ZIK/eRank, and seasonal demand.
Only propose unbranded or generic products with low counterfeit/VeRO risk; branded compatibility accessories are allowed if described as "compatible with".
Prefer sale prices of 18-60 in marketplace currency, light and small items, low return risk.
For every idea give honest estimates and an exact eBay search the seller can use with the "Sold items" filter to verify demand. Cite the URLs you relied on."""


class AIError(RuntimeError):
    pass


_ALLOWED_TAGS = {"h3", "h4", "p", "ul", "ol", "li", "strong", "b", "em", "i", "br", "table", "tr", "td", "th", "tbody"}
_VOID = {"br"}


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object"):
            self._skip += 1
        elif tag in _ALLOWED_TAGS and not self._skip:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object"):
            self._skip = max(0, self._skip - 1)
        elif tag in _ALLOWED_TAGS and tag not in _VOID and not self._skip:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(html.escape(data, quote=False))


def sanitize_html(doc: str) -> str:
    """Strip everything eBay disallows (active content, links, attributes)."""
    s = _Sanitizer()
    s.feed(doc)
    s.close()
    return re.sub(r"\n{3,}", "\n\n", "".join(s.out)).strip()


_BAD_TITLE_CHARS = re.compile(r"[!*~@#$%^=<>{}\[\]|\\]")


def clean_title(title: str, limit: int = 80) -> str:
    title = _BAD_TITLE_CHARS.sub("", html.unescape(title))
    title = re.sub(r"\s+", " ", title).strip(" -,/")
    if len(title) <= limit:
        return title
    cut = title[:limit]
    return cut[: cut.rfind(" ")].rstrip(" -,/") if " " in cut else cut


def _check_stop(response) -> None:
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise AIError(f"Model declined: {getattr(details, 'explanation', '') or 'refusal'}")
    if response.stop_reason == "max_tokens":
        raise AIError("Model output was truncated (max_tokens)")


class ListingWriter:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str = "claude-opus-5-5"):
        self.client = client or anthropic.Anthropic()
        self.model = model

    def write(self, product: SupplierProduct, marketplace: str = "EBAY_US", *, notes: str = "") -> ListingContent:
        language, _ = LOCALES.get(marketplace, LOCALES["EBAY_US"])
        attrs = "\n".join(f"- {k}: {v}" for k, v in product.attributes.items() if k not in ("sku_attr",))
        prompt = (
            f"Marketplace: {marketplace}\nLanguage: {language}\n\n"
            f"Supplier title: {product.title}\n"
            f"Supplier brand: {product.brand or 'none/unbranded'}\n"
            f"Attributes:\n{attrs or '- none'}\n\n"
            f"Supplier description (may be machine-translated, keep only facts):\n{product.description[:6000] or '(none)'}\n"
        )
        if notes:
            prompt += f"\nSeller notes: {notes}\n"
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=LISTING_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=ListingContent,
                output_config={"effort": "low"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Claude API unreachable: {exc}") from exc
        _check_stop(response)
        content = response.parsed_output
        if content is None:
            raise AIError("Model returned no structured listing")
        return content.model_copy(
            update={
                "title": clean_title(content.title),
                "description_html": sanitize_html(content.description_html),
            }
        )


class Researcher:
    """Finds candidate products using Claude with the web search server tool."""

    def __init__(self, client: anthropic.Anthropic | None = None, model: str = "claude-opus-5-5"):
        self.client = client or anthropic.Anthropic()
        self.model = model

    def run(self, marketplace: str = "EBAY_US", niche: str = "any", count: int = 1, exclude: list[str] | None = None) -> ResearchReport:
        language, currency = LOCALES.get(marketplace, LOCALES["EBAY_US"])
        ask = (
            f"Marketplace: {marketplace} (prices in {currency}). Niche: {niche}.\n"
            f"Find the {count} best product(s) to list this week, ranked best first.\n"
        )
        if exclude:
            ask += "Do not repeat these already-listed products: " + "; ".join(exclude[:200]) + "\n"
        messages: list = [{"role": "user", "content": ask}]
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}]
        # Raw schema + manual parse: intermediate text between searches must not be parsed as the report.
        output_config = {"effort": "high", "format": {"type": "json_schema", "schema": anthropic.transform_schema(ResearchReport)}}
        try:
            for _ in range(6):  # continue through pause_turn on long searches
                with self.client.beta.messages.stream(
                    model=self.model,
                    max_tokens=64000,
                    system=RESEARCH_SYSTEM,
                    messages=messages,
                    tools=tools,
                    output_config=output_config,
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                ) as stream:
                    response = stream.get_final_message()
                if response.stop_reason != "pause_turn":
                    break
                messages = [messages[0], {"role": "assistant", "content": response.content}]
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Claude API unreachable: {exc}") from exc
        _check_stop(response)
        texts = [b.text for b in response.content if b.type == "text" and b.text.strip()]
        for text in reversed(texts):
            try:
                return ResearchReport.model_validate_json(text)
            except ValueError:
                continue
        raise AIError("Research returned no structured report")
