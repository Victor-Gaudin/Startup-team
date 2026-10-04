import json
import time

import httpx2
import pytest

from dropkit import scoring, sourcing
from dropkit.engine import Engine
from dropkit.suppliers import import_product
from dropkit.suppliers.cj import CJClient, cj_product_id, parse_aging

# --- scoring -----------------------------------------------------------------


def test_strong_product_scores_high_with_revenue():
    r = scoring.evaluate(scoring.CheckInput(name="Magnetic car phone mount", supplier_cost=4, supplier_shipping=2,
                                            sale_price=16.99, delivery_days=6, sold_30d=180, active_listings=600, market_median=16.5))
    assert r.score >= 80 and r.verdict == "List it" and r.confidence == "high"
    assert r.units[0] < r.units[1] < r.units[2]
    assert r.revenue[1] == pytest.approx(r.units[1] * 16.99, abs=0.01)
    assert r.profit[1] == pytest.approx(r.units[1] * r.unit_profit, abs=0.01)
    assert sum(c.max_points for c in r.components) == 100


def test_unknowns_are_neutral_and_low_confidence():
    r = scoring.evaluate(scoring.CheckInput(name="Cable organizer kit", supplier_cost=4, supplier_shipping=2.5))
    assert r.confidence == "low" and r.units is None and r.revenue is None
    assert 40 <= r.score <= 70
    assert any("unknown" in c.note for c in r.components)


def test_weak_products_are_skipped():
    slow = scoring.evaluate(scoring.CheckInput(name="Desk lamp", supplier_cost=10, supplier_shipping=4, delivery_days=25,
                                               sold_30d=3, active_listings=900, market_median=15))
    assert slow.verdict.startswith("Skip") and slow.score < 50
    assert any("fewer than 10" in w for w in slow.warnings) and any("12 days" in w for w in slow.warnings)

    thin = scoring.evaluate(scoring.CheckInput(name="Cable", supplier_cost=9, sale_price=11.99, sold_30d=500))
    assert thin.verdict == "Skip - margin too thin"

    branded = scoring.evaluate(scoring.CheckInput(name="Genuine Apple AirPods case", supplier_cost=2, sold_30d=500))
    assert branded.verdict.startswith("Skip - brand") and branded.vero_risk == "high"


def test_share_model_monotonic():
    assert scoring.competition_share(25) > scoring.competition_share(400) > scoring.competition_share(1600)
    assert scoring.competition_share(1) == 0.15
    assert scoring.price_factor(10, 12) > scoring.price_factor(12, 12) > scoring.price_factor(15, 12)
    assert scoring.delivery_factor(4) > scoring.delivery_factor(8) > scoring.delivery_factor(20)


# --- CJdropshipping ----------------------------------------------------------

CJ_PRODUCT = {
    "pid": "04A22450-67F0-4617-A132-E7AE7F8963B0", "productNameEn": "Magnetic Car Phone Holder",
    "description": "<p>Strong <b>N52</b> magnets</p>", "productImageSet": ["https://cj/1.jpg", "https://cj/2.jpg", "https://cj/3.jpg"],
    "productWeight": 80, "sellPrice": "3.20-4.10",
    "variants": [
        {"vid": "V-SILVER", "variantNameEn": "Silver", "variantSellPrice": 4.10},
        {"vid": "V-BLACK", "variantNameEn": "Black", "variantSellPrice": 3.20},
    ],
}


def cj_handler(log, *, us_stock=40):
    def handler(req):
        path = req.url.path.split("/api2.0/v1/")[-1]
        log.append((req.method, path, dict(req.url.params), json.loads(req.content) if req.content else None, req.headers.get("CJ-Access-Token")))
        ok = lambda data: httpx2.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data})
        if path == "authentication/getAccessToken":
            return ok({"accessToken": "CJTOKEN", "accessTokenExpiryDate": "2099-01-01T00:00:00+08:00", "refreshToken": "R"})
        if path == "product/query":
            return ok(CJ_PRODUCT) if req.url.params.get("pid") == CJ_PRODUCT["pid"] else ok(None)
        if path == "product/stock/queryByVid":
            return ok([{"countryCode": "US", "totalInventoryNum": us_stock}, {"countryCode": "CN", "totalInventoryNum": 9000}])
        if path == "logistic/freightCalculate":
            body = json.loads(req.content)
            if body["startCountryCode"] == "US":
                return ok([{"logisticName": "USPS+", "logisticPrice": 4.10, "logisticAging": "2-5"},
                           {"logisticName": "CJ Economy US", "logisticPrice": 2.60, "logisticAging": "5-8"}])
            return ok([{"logisticName": "CJPacket Ordinary", "logisticPrice": 2.20, "logisticAging": "8-15"}])
        if path == "product/listV2":
            local = "countryCode" in req.url.params
            items = [{"id": "04A22450-67F0-4617-A132-E7AE7F8963B0", "nameEn": "Magnetic Car Phone Holder", "sellPrice": "3.20"}] if local else \
                [{"id": "04A22450-67F0-4617-A132-E7AE7F8963B0", "nameEn": "dup"}, {"id": "BAD-PID", "nameEn": "Other holder", "sellPrice": "2.10"}]
            return ok({"content": [{"productList": items}]})
        if path == "shopping/order/createOrderV2":
            return ok({"orderId": "CJ-ORDER-1"})
        if path == "shopping/order/getOrderDetail":
            return ok({"orderId": "CJ-ORDER-1", "trackNumber": "9400111", "logisticName": "USPS"})
        return httpx2.Response(200, json={"code": 1600001, "result": False, "message": "not found", "data": None})
    return handler


def test_cj_ids_and_aging():
    assert cj_product_id("https://cjdropshipping.com/product/magnetic-holder-p-04A22450-67F0-4617-A132-E7AE7F8963B0.html") == "04A22450-67F0-4617-A132-E7AE7F8963B0"
    assert cj_product_id("cj:ABC123") == "ABC123"
    assert parse_aging("3-7") == (3, 7) and parse_aging("12") == (12, 12) and parse_aging(None) == (None, None)


def test_cj_product_prefers_local_warehouse_and_fast_shipping(db):
    log = []
    cj = CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler(log))))
    p = cj.get_product("04A22450-67F0-4617-A132-E7AE7F8963B0", ship_to="US")
    assert p.supplier == "cj" and p.price == 3.20 and p.attributes["vid"] == "V-BLACK"  # cheapest variant
    assert p.ships_from == "US" and p.stock_qty == 40 and p.in_stock
    # USPS+ is $1.50 more than the cheapest but 3 days faster -> chosen
    assert p.shipping_method == "USPS+" and p.shipping_days == 5 and p.shipping_cost == 4.10
    assert p.description == "Strong N52 magnets" and len(p.images) == 3
    assert log[1][4] == "CJTOKEN" and db.get_token("cj_access")[0] == "CJTOKEN"
    # token is cached: a second client reuses it from the database without re-authenticating
    log.clear()
    CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler(log)))).get_product("04A22450-67F0-4617-A132-E7AE7F8963B0")
    assert all(entry[1] != "authentication/getAccessToken" for entry in log)


def test_cj_falls_back_to_china_when_no_local_stock(db):
    cj = CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler([], us_stock=0))))
    p = cj.get_product("04A22450-67F0-4617-A132-E7AE7F8963B0", ship_to="US", vid="V-SILVER")
    assert p.attributes["vid"] == "V-SILVER" and p.price == 4.10
    assert p.ships_from == "CN" and p.shipping_days == 15 and p.shipping_method == "CJPacket Ordinary"


def test_cj_offers_and_comparison_sorting(db):
    cj = CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler([]))))
    result = sourcing.compare("magnetic car mount", ship_to="US", cj=cj)
    assert [o.product_id for o in result.offers] == ["04A22450-67F0-4617-A132-E7AE7F8963B0", "BAD-PID"]  # deduped, fast first
    fast = result.offers[0]
    assert fast.ships_from == "US" and fast.shipping_days_max == 5 and fast.auto_order and fast.landed_cost == 7.30
    assert "details unavailable" in result.offers[1].note
    names = [link.name for link in result.links]
    assert names[0] == "CJdropshipping" and "AliExpress (US warehouse)" in names and "Walmart" in names
    assert "shipFromCountry=US" in result.links[1].url

    no_cj = sourcing.compare("x", ship_to="FR")
    assert not no_cj.offers and "CJ_API_KEY" in no_cj.errors[0] and all(l.name != "Walmart" for l in no_cj.links)


def test_cj_errors():
    def handler(req):
        return httpx2.Response(200, json={"code": 1600100, "result": False, "message": "Invalid API key", "data": None})
    cj = CJClient("bad", http=httpx2.Client(transport=httpx2.MockTransport(handler)))
    with pytest.raises(Exception, match="Invalid API key"):
        cj.get_product("x")


def test_import_routes_cj_urls(settings, db):
    settings.cj_api_key = "key"
    cj = CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler([]))))
    p = import_product("https://cjdropshipping.com/product/x-p-04A22450-67F0-4617-A132-E7AE7F8963B0.html", settings, cj=cj)
    assert p.supplier == "cj" and p.url.startswith("https://cjdropshipping.com")
    p2 = import_product("cj:04A22450-67F0-4617-A132-E7AE7F8963B0", settings, cj=cj)
    assert p2.url.endswith("-p-04A22450-67F0-4617-A132-E7AE7F8963B0.html")


# --- engine: CJ auto-order + verification -------------------------------------


def test_engine_cj_auto_order_and_tracking(settings, db, http, router):
    from tests.test_engine import FakeWriter, _ebay_order, ebay_routes
    from dropkit.ebay import EbayClient

    db.set_token("user_refresh", "refresh", time.time() + 10**7)
    state = {}
    ebay_routes(router, state)
    ebay = EbayClient.from_settings(settings, db, http=http)
    ebay.min_interval = 0
    log = []
    cj = CJClient("key", db=db, http=httpx2.Client(transport=httpx2.MockTransport(cj_handler(log))))
    eng = Engine(settings, db, ebay=ebay, ali=None, cj=cj, writer=FakeWriter())

    sku = eng.add_product(cj.get_product("04A22450-67F0-4617-A132-E7AE7F8963B0"))
    eng.prepare(sku)
    eng.publish(sku)
    state["orders"] = [_ebay_order(sku, total="19.99")]
    stats = eng.sync_orders()
    assert stats["ordered"] == 1 and stats["shipped"] == 1  # CJ already had tracking, pushed in the same run
    order_call = next(e for e in log if e[1] == "shopping/order/createOrderV2")[3]
    assert order_call["products"] == [{"vid": "V-BLACK", "quantity": 1}]
    assert order_call["fromCountryCode"] == "US" and order_call["logisticName"] == "USPS+"
    assert order_call["shippingZip"] == "78701" and order_call["shippingCustomerName"] == "Jane Doe"
    assert order_call["orderNumber"] == "O-1-L-1"
    assert state["shipped"]["trackingNumber"] == "9400111" and state["shipped"]["shippingCarrierCode"] == "USPS"


def test_engine_verify_fills_market_data_and_candidates(settings, db, http, router, tmp_path):
    from tests.test_engine import ebay_routes
    from dropkit.ebay import EbayClient

    state = {}
    ebay_routes(router, state)
    router.routes.insert(0, ("GET", "/buy/browse/v1/item_summary/search", {"total": 420, "itemSummaries": [
        {"price": {"value": "15.99"}}, {"price": {"value": "16.99"}, "shippingOptions": [{"shippingCost": {"value": "1.00"}}]},
        {"price": {"value": "19.99"}}]}))
    ebay = EbayClient.from_settings(settings, db, http=http)
    ebay.min_interval = 0
    eng = Engine(settings, db, ebay=ebay, ali=None, cj=None)

    cid, inp, r = eng.verify(scoring.CheckInput(name="Magnetic car phone mount", supplier_cost=4, supplier_shipping=2, sold_30d=150))
    assert inp.active_listings == 420 and inp.market_median == 17.99
    assert r.units is not None and any("asking prices" in w for w in r.warnings)
    stored = db.check(cid)
    assert stored["score"] == r.score and json.loads(stored["input"])["active_listings"] == 420

    with pytest.raises(ValueError, match="Supplier cost"):
        eng.verify(scoring.CheckInput(name="x", supplier_cost=0))

    f = tmp_path / "c.json"
    f.write_text(json.dumps([{"name": "Magnetic car phone mount", "supplier_cost": 4},
                             {"name": "Headset stand", "supplier_cost": 6.5, "supplier_shipping": 3.5, "delivery_days": 7, "extra": 1}]))
    assert eng.load_candidates(f) == 1  # existing name skipped, unknown keys ignored
    assert eng.load_candidates(f) == 0
    assert {row["source"] for row in db.checks()} == {"manual", "research"}


def test_repo_candidates_file_is_valid(settings, db):
    from pathlib import Path
    eng = Engine(settings, db, ebay=None, ali=None, cj=None)
    eng.ebay = None
    assert eng.load_candidates(Path(__file__).resolve().parents[1] / "research" / "candidates.json") == 15
    for row in db.checks():
        r = json.loads(row["result"])
        assert r["vero_risk"] != "high", row["name"]
