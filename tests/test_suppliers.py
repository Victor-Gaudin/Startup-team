import json

import httpx2
import pytest

from dropkit.suppliers import detect_supplier, import_product
from dropkit.suppliers.aliexpress import AliExpressClient, aliexpress_product_id, ebay_address_to_aliexpress, sign
from dropkit.suppliers.csv_feed import read_feed
from dropkit.suppliers.generic import FetchError, _to_float, fetch_product_page, parse_product_html

JSONLD_PAGE = """<html><head><title>x</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"BreadcrumbList"},
{"@type":"Product","name":"Support Telephone Voiture Magnetique","sku":"CD123","brand":{"@type":"Brand","name":"Generique"},
"image":["https://img/1.jpg","https://img/2.jpg"],"description":"Aimant puissant &amp; rotation 360",
"offers":{"@type":"Offer","price":"12,99","priceCurrency":"EUR","availability":"https://schema.org/InStock",
"shippingDetails":{"shippingRate":{"value":"2.50","currency":"EUR"}}}}]}</script></head><body></body></html>"""

OG_PAGE = """<html><head><meta property="og:title" content="Cable Organizer Kit">
<meta property="product:price:amount" content="7.49"><meta property="product:price:currency" content="USD">
<meta property="og:image" content="https://img/a.jpg"></head></html>"""

AMAZON_PAGE = """<html><span id="productTitle">  USB C Cable 6ft 2-Pack Braided  </span>
<span class="a-price"><span class="a-offscreen">$9.99</span></span>"hiRes":"https://m.media-amazon.com/1.jpg","hiRes":"https://m.media-amazon.com/2.jpg"</html>"""


def test_detect_supplier():
    assert detect_supplier("https://www.aliexpress.us/item/1005001.html") == "aliexpress"
    assert detect_supplier("https://www.amazon.fr/dp/B0") == "amazon"
    assert detect_supplier("https://www.cdiscount.com/x.html") == "cdiscount"
    assert detect_supplier("https://shop.example.com/p/1") == "generic"


def test_jsonld_parse():
    p = parse_product_html(JSONLD_PAGE, "https://www.cdiscount.com/p.html")
    assert p.title == "Support Telephone Voiture Magnetique"
    assert p.price == 12.99 and p.currency == "EUR" and p.shipping_cost == 2.5
    assert p.images == ["https://img/1.jpg", "https://img/2.jpg"]
    assert p.brand == "Generique" and p.supplier_sku == "CD123" and p.in_stock
    assert "&" in p.description


def test_og_and_amazon_fallback():
    p = parse_product_html(OG_PAGE, "https://shop/p")
    assert (p.title, p.price, p.images) == ("Cable Organizer Kit", 7.49, ["https://img/a.jpg"])
    a = parse_product_html(AMAZON_PAGE, "https://www.amazon.com/dp/B0X")
    assert a.supplier == "amazon" and a.price == 9.99 and len(a.images) == 2
    assert a.title == "USB C Cable 6ft 2-Pack Braided"


def test_parse_failure():
    with pytest.raises(FetchError):
        parse_product_html("<html>captcha</html>", "https://x")


@pytest.mark.parametrize("raw,val", [("12,99", 12.99), ("1.299,00", 1299.0), ("1,299.00", 1299.0), ("$9.99", 9.99), ("1,299", 1299.0), ("", None)])
def test_to_float(raw, val):
    assert _to_float(raw) == val


def test_fetch_uses_original_url():
    http = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200, text=JSONLD_PAGE)))
    p = fetch_product_page("https://www.cdiscount.com/p.html?ref=1", http=http)
    assert p.url == "https://www.cdiscount.com/p.html?ref=1"
    blocked = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(503, text="no")))
    with pytest.raises(FetchError):
        fetch_product_page("https://x/p", http=blocked)


def test_aliexpress_id_and_sign():
    assert aliexpress_product_id("https://www.aliexpress.com/item/1005006123456789.html?spm=a") == "1005006123456789"
    assert aliexpress_product_id("https://fr.aliexpress.com/item/1005006123456789.html") == "1005006123456789"
    assert aliexpress_product_id("https://example.com") is None
    import hashlib, hmac
    params = {"b": "2", "a": "1", "method": "x.y"}
    expected = hmac.new(b"s", b"a1b2methodx.y", hashlib.sha256).hexdigest().upper()
    assert sign(params, "s") == expected


ALI_PRODUCT = {
    "aliexpress_ds_product_get_response": {
        "rsp_code": "200",
        "result": {
            "ae_item_base_info_dto": {"subject": "Magnetic Phone Holder", "detail": "<p>Strong <b>magnet</b></p>", "avg_evaluation_rating": "4.8", "evaluation_count": "3021"},
            "ae_item_sku_info_dtos": {"ae_item_sku_info_d_t_o": [
                {"sku_id": "111", "offer_sale_price": "4.10", "sku_available_stock": 0, "currency_code": "USD",
                 "ae_sku_property_dtos": {"ae_sku_property_d_t_o": [{"sku_property_id": 14, "property_value_id": 29}]}},
                {"sku_id": "222", "offer_sale_price": "4.50", "sku_available_stock": 500, "currency_code": "USD",
                 "ae_sku_property_dtos": {"ae_sku_property_d_t_o": [{"sku_property_id": 14, "property_value_id": 193, "property_value_definition_name": "Black"}]}},
            ]},
            "ae_multimedia_info_dto": {"image_urls": "https://ae/1.jpg;https://ae/2.jpg;https://ae/3.jpg"},
            "ae_item_properties": {"ae_item_property": [{"attr_name": "Brand Name", "attr_value": "NoEnName_Null"}, {"attr_name": "Material", "attr_value": "ABS"}]},
            "logistics_info_dto": {"delivery_time": 7},
            "ae_store_info": {"store_name": "Best Store", "shipping_speed_rating": "4.7"},
        },
    }
}


def test_aliexpress_product_and_order():
    seen = []

    def handler(req):
        form = dict(httpx2.QueryParams(req.content.decode()))
        seen.append(form)
        assert form["sign"] == sign({k: v for k, v in form.items() if k != "sign"}, "as")
        if form["method"] == "aliexpress.ds.product.get":
            return httpx2.Response(200, json=ALI_PRODUCT)
        if form["method"] == "aliexpress.ds.order.create":
            req_obj = json.loads(form["param_place_order_request4_open_api_d_t_o"])
            assert req_obj["product_items"][0]["sku_attr"] == "14:193#Black"
            return httpx2.Response(200, json={"aliexpress_ds_order_create_response": {"result": {"is_success": True, "order_list": [8123]}}})
        if form["method"] == "aliexpress.trade.ds.order.get":
            return httpx2.Response(200, json={"aliexpress_trade_ds_order_get_response": {"result": {"logistics_info_list": [{"logistics_no": "LX1US", "logistics_service": "USPS"}]}}})
        return httpx2.Response(200, json={"error_response": {"code": "x", "msg": "bad"}})

    client = AliExpressClient("ak", "as", "at", http=httpx2.Client(transport=httpx2.MockTransport(handler)))
    p = client.get_product("1005", url="https://www.aliexpress.com/item/1005.html")
    assert p.price == 4.50 and p.in_stock and p.stock_qty == 500  # cheapest IN-STOCK variant
    assert p.supplier_sku == "1005:222" and p.attributes["sku_attr"] == "14:193#Black"
    assert len(p.images) == 3 and p.shipping_days == 7 and p.attributes["Material"] == "ABS"
    assert "<" not in p.description
    first = client.get_product("1005", sku_id="111")
    assert first.price == 4.10 and not first.in_stock

    placed = client.place_order(product_id="1005", sku_attr_value="14:193#Black", quantity=1, address={"full_name": "A"})
    assert placed.ok and placed.order_ids == ["8123"]
    assert client.order_tracking("8123") == ("LX1US", "USPS")
    assert seen[0]["simplify"] == "true" and seen[0]["sign_method"] == "sha256"


def test_import_product_routes_aliexpress_to_api(settings):
    http = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json=ALI_PRODUCT)))
    ali = AliExpressClient("ak", "as", "at", http=http)
    p = import_product("https://www.aliexpress.com/item/1005006123456789.html", settings, ali=ali)
    assert p.supplier == "aliexpress" and p.price == 4.50


def test_address_mapping():
    addr = ebay_address_to_aliexpress({
        "fullName": "Jane Doe",
        "contactAddress": {"addressLine1": "1 Main St", "city": "Austin", "stateOrProvince": "TX", "postalCode": "78701", "countryCode": "US"},
        "primaryPhone": {"phoneNumber": "+1 (512) 555-0100"},
    })
    assert addr["full_name"] == "Jane Doe" and addr["zip"] == "78701" and addr["mobile_no"] == "5125550100"
    assert addr["country"] == "US" and addr["province"] == "TX"


def test_csv_feed(tmp_path):
    f = tmp_path / "feed.csv"
    f.write_text("sku,title,price,shipping_cost,stock,images,shipping_days\nW1,Cable Kit,3.20,1.00,40,https://a.jpg|https://b.jpg,4\nW2,Stand,5,,0,,\n")
    items = read_feed(f, supplier="wholesaler")
    assert items[0].price == 3.2 and items[0].stock_qty == 40 and items[0].images == ["https://a.jpg", "https://b.jpg"]
    assert items[0].shipping_days == 4 and items[0].supplier == "wholesaler"
    assert items[1].in_stock is False
    bad = tmp_path / "bad.csv"
    bad.write_text("title,price\n,3\n")
    with pytest.raises(ValueError):
        read_feed(bad)
