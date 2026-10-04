"""End-to-end flow against mocked eBay + AliExpress APIs."""

import json
import time

import httpx2
import pytest

from dropkit.ebay import EbayClient, EbayError
from dropkit.engine import Engine, carrier_code
from dropkit.models import ItemSpecific, ListingContent, SupplierProduct
from dropkit.suppliers.aliexpress import AliExpressClient


class FakeWriter:
    def __init__(self, title="Magnetic Car Phone Mount Dashboard Holder 360 Rotation"):
        self.title = title

    def write(self, product, marketplace, notes=""):
        return ListingContent(title=self.title, description_html="<p>Strong magnet</p>",
                              item_specifics=[ItemSpecific(name="Type", value="Car Mount")], search_keywords=["car phone mount"])


class FakeAli:
    def __init__(self, price=4.5, in_stock=True):
        self.price, self.in_stock, self.orders, self.tracking = price, in_stock, [], None

    def get_product(self, product_id, url="", ship_to="US", sku_id=None):
        return SupplierProduct(supplier="aliexpress", url=url or f"https://www.aliexpress.com/item/{product_id}.html",
                               supplier_sku=f"{product_id}:{sku_id or '222'}", title="Magnetic Holder", price=self.price,
                               in_stock=self.in_stock, stock_qty=100 if self.in_stock else 0,
                               images=["https://a/1.jpg", "https://a/2.jpg", "https://a/3.jpg"], attributes={"sku_attr": "14:193"})

    def place_order(self, **kw):
        from dropkit.suppliers.aliexpress import PlacedOrder
        self.orders.append(kw)
        return PlacedOrder(True, ["AE1"])

    def order_tracking(self, order_id):
        return self.tracking


def ebay_routes(router, state):
    router.add("POST", "/identity/v1/oauth2/token", {"access_token": "tok", "expires_in": 7200})
    router.add("GET", "get_default_category_tree_id", {"categoryTreeId": "0"})
    router.add("GET", "get_category_suggestions", {"categorySuggestions": [{"category": {"categoryId": "35190", "categoryName": "Mounts & Holders"}}]})
    router.add("GET", "/buy/browse/v1/item_summary/search", {"itemSummaries": [
        {"title": "a", "price": {"value": "14.99"}, "shippingOptions": [{"shippingCost": {"value": "0"}}]},
        {"title": "b", "price": {"value": "16.99"}},
        {"title": "c", "price": {"value": "18.50"}},
    ]})

    def put_item(req):
        state["item"] = json.loads(req.content)
        return httpx2.Response(204)

    router.add("PUT", "/sell/inventory/v1/inventory_item/", put_item)

    def post_offer(req):
        state["offer"] = json.loads(req.content)
        return {"offerId": "OFF1"}

    router.add("POST", "/sell/inventory/v1/offer/OFF1/publish", {"listingId": "1100223344"})
    router.add("PUT", "/sell/inventory/v1/offer/OFF1", lambda req: httpx2.Response(204))
    router.add("POST", "/sell/inventory/v1/offer", post_offer)

    def bulk(req):
        state.setdefault("bulk", []).append(json.loads(req.content))
        return {"responses": [{"statusCode": 200}]}

    router.add("POST", "bulk_update_price_quantity", bulk)
    router.add("GET", "/sell/fulfillment/v1/order", lambda req: {"orders": state.get("orders", [])})

    def ship(req):
        state["shipped"] = json.loads(req.content)
        return (201, {"fulfillmentId": "FUL1"})

    router.add("POST", "/shipping_fulfillment", ship)


@pytest.fixture
def engine(settings, db, http, router):
    db.set_token("user_refresh", "refresh", time.time() + 10**7)
    state = {}
    ebay_routes(router, state)
    ebay = EbayClient.from_settings(settings, db, http=http)
    ebay.min_interval = 0
    eng = Engine(settings, db, ebay=ebay, ali=FakeAli(), writer=FakeWriter())
    eng._state = state
    return eng


def test_full_listing_flow(engine, router):
    sku = engine.add_product(engine.ali.get_product("1005", url="https://www.aliexpress.com/item/1005.html"))
    assert sku == "DK-00001"

    r = engine.prepare(sku)
    assert r.vero.risk == "low"
    assert r.margin.margin >= 0.2 and str(r.price).endswith(".99")
    assert len(r.competitors) == 3

    listing_id = engine.publish(sku)
    assert listing_id == "1100223344"
    item, offer = engine._state["item"], engine._state["offer"]
    assert item["product"]["aspects"]["Brand"] == ["Unbranded"] and item["product"]["aspects"]["Type"] == ["Car Mount"]
    assert offer["categoryId"] == "35190" and offer["pricingSummary"]["price"]["currency"] == "USD"
    assert offer["listingPolicies"] == {"fulfillmentPolicyId": "F1", "paymentPolicyId": "P1", "returnPolicyId": "R1"}
    row = engine.db.listing(sku)
    assert row["status"] == "published" and row["offer_id"] == "OFF1"
    # re-publishing updates the live listing through the same offer and does not count against the daily cap
    engine.daily_publish_limit = 1
    assert engine.publish(sku) == "1100223344"
    assert [e["kind"] for e in engine.db.events()][:2] == ["update", "publish"]
    auth = [c for c in router.calls if "/sell/" in str(c.url)][0].headers
    assert auth["authorization"] == "Bearer tok" and auth["x-ebay-c-marketplace-id"] == "EBAY_US"


def test_vero_block_prevents_publish(engine):
    engine._writer = FakeWriter("Genuine Apple iPhone 17 Case")
    sku = engine.add_product(engine.ali.get_product("1005"))
    r = engine.prepare(sku)
    assert r.vero.blocked and engine.db.listing(sku)["status"] == "blocked"
    with pytest.raises(ValueError, match="VeRO"):
        engine.publish(sku)


def test_low_margin_prevents_publish(engine):
    sku = engine.add_product(engine.ali.get_product("1005"))
    engine.prepare(sku, price=6.0)
    with pytest.raises(ValueError, match="margin"):
        engine.publish(sku)


def _ebay_order(sku, total="16.99"):
    return {"orderId": "O-1", "lineItems": [{"lineItemId": "L-1", "sku": sku, "quantity": 1, "total": {"value": total}}],
            "fulfillmentStartInstructions": [{"shippingStep": {"shipTo": {
                "fullName": "Jane Doe", "contactAddress": {"addressLine1": "1 Main", "city": "Austin", "stateOrProvince": "TX",
                                                           "postalCode": "78701", "countryCode": "US"},
                "primaryPhone": {"phoneNumber": "5125550100"}}}}]}


def test_order_auto_order_and_tracking(engine):
    sku = engine.add_product(engine.ali.get_product("1005", url="https://www.aliexpress.com/item/1005.html"))
    engine.prepare(sku)
    engine.publish(sku)
    engine._state["orders"] = [_ebay_order(sku), _ebay_order("OTHER-SKU")]

    stats = engine.sync_orders()
    assert stats["new"] == 1 and stats["ordered"] == 1
    assert engine.ali.orders[0]["address"]["zip"] == "78701" and engine.ali.orders[0]["sku_attr_value"] == "14:193"

    # running again does not duplicate the order
    assert engine.sync_orders()["new"] == 0

    engine.ali.tracking = ("LX123US", "USPS")
    assert engine.sync_orders()["shipped"] == 1
    shipped = engine._state["shipped"]
    assert shipped["trackingNumber"] == "LX123US" and shipped["shippingCarrierCode"] == "USPS"
    assert shipped["lineItems"] == [{"lineItemId": "L-1", "quantity": 1}]
    assert engine.db.orders()[0]["status"] == "shipped"


def test_order_skips_auto_order_when_unprofitable(engine):
    sku = engine.add_product(engine.ali.get_product("1005"))
    engine.prepare(sku)
    engine.publish(sku)
    engine.ali.price = 30.0  # supplier price exploded after the sale
    engine._state["orders"] = [_ebay_order(sku, total="16.99")]
    stats = engine.sync_orders()
    assert stats["manual"] == 1 and not engine.ali.orders
    assert "lose" in engine.db.orders()[0]["note"]


def test_manual_order_for_non_api_supplier(engine):
    sku = engine.add_product(SupplierProduct(supplier="amazon", url="https://www.amazon.com/dp/B0", title="Cable", price=5,
                                             images=["https://x/1.jpg"]))
    engine.prepare(sku)
    engine.publish(sku)
    engine._state["orders"] = [_ebay_order(sku)]
    assert engine.sync_orders()["manual"] == 1
    key = engine.db.orders()[0]["ebay_order_id"]
    engine.add_tracking(key, "1Z999", "UPS Ground")
    assert engine._state["shipped"]["shippingCarrierCode"] == "UPS"


def test_monitor_reprice_pause_restock(engine):
    sku = engine.add_product(engine.ali.get_product("1005"))
    engine.prepare(sku)
    engine.publish(sku)
    old_price = engine.db.listing(sku)["price"]

    engine.ali.price = 5.0  # small cost increase -> reprice
    actions = engine.monitor()
    new_price = engine.db.listing(sku)["price"]
    assert new_price > old_price and "repriced" in actions[0]

    engine.ali.in_stock = False
    actions = engine.monitor()
    assert engine.db.listing(sku)["status"] == "paused" and "out of stock" in actions[0]
    assert engine._state["bulk"][-1]["requests"][0]["shipToLocationAvailability"]["quantity"] == 0

    engine.ali.in_stock = True
    actions = engine.monitor()
    assert engine.db.listing(sku)["status"] == "published" and "restocked" in actions[0]

    engine.ali.price = 20.0  # huge jump -> pause for review instead of a 3x price
    actions = engine.monitor()
    assert engine.db.listing(sku)["status"] == "paused" and "review" in actions[0]


def test_retry_on_429(settings, db, router, http):
    db.set_token("user_refresh", "r", time.time() + 10**7)
    hits = []

    def flaky(req):
        hits.append(1)
        return httpx2.Response(429, headers={"retry-after": "0"}) if len(hits) < 3 else httpx2.Response(200, json={"ok": True})

    router.add("POST", "oauth2/token", {"access_token": "t", "expires_in": 7200})
    router.add("GET", "/sell/account/v1/", flaky)
    ebay = EbayClient.from_settings(settings, db, http=http)
    ebay.min_interval = 0
    assert ebay.request("GET", "/sell/account/v1/x") == {"ok": True}
    assert len(hits) == 3


def test_ebay_error_and_consent_url(settings, db, router, http):
    router.add("POST", "oauth2/token", {"access_token": "t", "expires_in": 7200})
    ebay = EbayClient.from_settings(settings, db, http=http)
    with pytest.raises(EbayError, match="not connected"):
        ebay.request("GET", "/sell/x")
    db.set_token("user_refresh", "r", time.time() + 10**7)
    with pytest.raises(EbayError) as err:
        ebay.request("GET", "/sell/missing", retries=0)
    assert err.value.status == 404
    url = ebay.consent_url()
    assert url.startswith("https://auth.sandbox.ebay.com/oauth2/authorize") and "sell.inventory" in url


def test_carrier_code():
    assert carrier_code("USPS First Class") == "USPS"
    assert carrier_code("Cainiao Super Economy") == "Cainiao"
    assert carrier_code("Mystery Post") == "Other"
