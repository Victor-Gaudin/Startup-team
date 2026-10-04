"""Parse a public product page into a SupplierProduct.

Strategy, most to least reliable:
1. schema.org Product in JSON-LD (Cdiscount, most shops, sometimes Amazon)
2. OpenGraph / product meta tags
3. Site-specific fallbacks for Amazon and AliExpress markup

Large retailers block bots aggressively; set DROPKIT_SCRAPER_PROXY to a
residential/scraping proxy (e.g. OxyLabs) if fetches return captchas.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Any

import httpx2 as httpx

from ..models import SupplierProduct

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}


class FetchError(RuntimeError):
    pass


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self.title = ""
        self._in_jsonld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and "content" in a:
                self.meta.setdefault(key.lower(), a["content"])
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._buf.append(data)
        elif self._in_title:
            self.title += data


def _iter_jsonld_nodes(obj: Any):
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_jsonld_nodes(item)
    elif isinstance(obj, dict):
        yield obj
        if "@graph" in obj:
            yield from _iter_jsonld_nodes(obj["@graph"])


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(str(x).lower() in ("product", "productgroup") for x in types)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "").replace(" ", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        # whichever separator comes last is the decimal separator
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) in (1, 2) else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _images(value: Any) -> list[str]:
    out: list[str] = []
    for v in value if isinstance(value, list) else [value]:
        if isinstance(v, dict):
            v = v.get("url") or v.get("contentUrl")
        if isinstance(v, str) and v.startswith("http"):
            out.append(v)
    return out


def _from_jsonld(node: dict, url: str) -> SupplierProduct | None:
    offers = node.get("offers") or {}
    offer = _first(offers) if isinstance(offers, list) else offers
    if isinstance(offer, dict) and offer.get("@type") == "AggregateOffer":
        price = _to_float(offer.get("lowPrice") or offer.get("price"))
    else:
        price = _to_float(offer.get("price") if isinstance(offer, dict) else None)
    if price is None and isinstance(offer, dict):
        spec = offer.get("priceSpecification")
        price = _to_float(_first(spec).get("price")) if isinstance(_first(spec), dict) else None
    if price is None or not node.get("name"):
        return None
    availability = str(offer.get("availability", "")) if isinstance(offer, dict) else ""
    brand = node.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    shipping = 0.0
    if isinstance(offer, dict):
        details = _first(offer.get("shippingDetails"))
        if isinstance(details, dict):
            rate = details.get("shippingRate")
            shipping = _to_float(rate.get("value") if isinstance(rate, dict) else None) or 0.0
    return SupplierProduct(
        supplier="generic",
        url=url,
        supplier_sku=str(node.get("sku") or node.get("productID") or ""),
        title=html.unescape(str(node["name"])).strip(),
        description=html.unescape(str(node.get("description") or "")).strip(),
        price=price,
        shipping_cost=shipping,
        currency=str(offer.get("priceCurrency") or "USD") if isinstance(offer, dict) else "USD",
        in_stock=("outofstock" not in availability.lower() and "soldout" not in availability.lower()),
        images=_images(node.get("image")),
        brand=str(brand or ""),
        gtin=str(node.get("gtin13") or node.get("gtin12") or node.get("gtin") or node.get("ean") or ""),
    )


_AMAZON_TITLE = re.compile(r'id="productTitle"[^>]*>\s*([^<]+?)\s*<', re.S)
_AMAZON_PRICE = re.compile(r'class="a-offscreen">\s*([^<]+?)\s*<')
_AMAZON_IMG = re.compile(r'"hiRes":"(https://[^"]+)"')
_ALI_PRICE = re.compile(r'"(?:minActivityAmount|minAmount)"\s*:\s*\{[^}]*?"value"\s*:\s*"?([\d.]+)')
_ALI_TITLE = re.compile(r'"subject"\s*:\s*"([^"]+)"')
_ALI_IMGS = re.compile(r'"imagePathList"\s*:\s*\[([^\]]*)\]')


def _site_fallback(doc: str, url: str) -> SupplierProduct | None:
    if "amazon." in url:
        t, p = _AMAZON_TITLE.search(doc), _AMAZON_PRICE.search(doc)
        if t and p and _to_float(p.group(1)) is not None:
            return SupplierProduct(
                supplier="amazon", url=url, title=html.unescape(t.group(1)), price=_to_float(p.group(1)) or 0.0,
                images=list(dict.fromkeys(_AMAZON_IMG.findall(doc)))[:8],
                in_stock="currently unavailable" not in doc.lower(),
            )
    if "aliexpress." in url:
        t, p = _ALI_TITLE.search(doc), _ALI_PRICE.search(doc)
        if t and p and _to_float(p.group(1)) is not None:
            imgs = _ALI_IMGS.search(doc)
            images = re.findall(r'"(https?:[^"]+)"', imgs.group(1)) if imgs else []
            return SupplierProduct(
                supplier="aliexpress", url=url, title=html.unescape(t.group(1)), price=_to_float(p.group(1)) or 0.0,
                images=images[:8],
            )
    return None


def parse_product_html(doc: str, url: str) -> SupplierProduct:
    parser = _HeadParser()
    parser.feed(doc)

    for block in parser.jsonld:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        for node in _iter_jsonld_nodes(data):
            if _is_product(node):
                if node.get("@type") == "ProductGroup" and node.get("hasVariant"):
                    variant = _first(node["hasVariant"])
                    if isinstance(variant, dict):
                        node = {**node, **{k: v for k, v in variant.items() if k in ("offers", "sku", "image")}}
                product = _from_jsonld(node, url)
                if product:
                    return product

    m = parser.meta
    price = _to_float(m.get("product:price:amount") or m.get("og:price:amount") or m.get("price"))
    title = m.get("og:title") or parser.title.strip()
    if price is not None and title:
        return SupplierProduct(
            supplier="generic",
            url=url,
            title=html.unescape(title),
            description=html.unescape(m.get("og:description") or m.get("description") or ""),
            price=price,
            currency=m.get("product:price:currency") or m.get("og:price:currency") or "USD",
            images=[m["og:image"]] if m.get("og:image") else [],
            brand=m.get("product:brand") or m.get("og:brand") or "",
            in_stock="out of stock" not in (m.get("product:availability") or m.get("og:availability") or "").lower(),
        )

    fallback = _site_fallback(doc, url)
    if fallback:
        return fallback
    raise FetchError(f"No product data found on {url} (blocked page, captcha, or unsupported layout)")


def fetch_product_page(url: str, *, proxy: str | None = None, http: httpx.Client | None = None) -> SupplierProduct:
    client = http or httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, proxy=proxy)
    try:
        resp = client.get(url, headers=HEADERS)
    finally:
        if http is None:
            client.close()
    if resp.status_code >= 400:
        raise FetchError(f"HTTP {resp.status_code} fetching {url}")
    if "captcha" in resp.text[:20000].lower() and "productTitle" not in resp.text:
        raise FetchError(f"Captcha/bot wall on {url}; configure DROPKIT_SCRAPER_PROXY")
    return parse_product_html(resp.text, url)
