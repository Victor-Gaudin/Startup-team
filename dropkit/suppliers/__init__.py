"""Supplier adapters: turn a product URL or feed row into a SupplierProduct, and place orders where an API allows it."""

from __future__ import annotations

from urllib.parse import urlparse

from ..config import Settings
from ..models import SupplierProduct
from .aliexpress import AliExpressClient, aliexpress_product_id
from .cj import CJClient, cj_product_id
from .generic import fetch_product_page


def detect_supplier(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "aliexpress." in host:
        return "aliexpress"
    if "cjdropshipping." in host or url.startswith("cj:"):
        return "cj"
    if "amazon." in host:
        return "amazon"
    if "cdiscount." in host:
        return "cdiscount"
    return "generic"


def import_product(url: str, settings: Settings, *, http=None, ali: AliExpressClient | None = None,
                   cj: CJClient | None = None) -> SupplierProduct:
    """Import a product from any supported URL.

    AliExpress and CJdropshipping use their official APIs when credentials are
    set (accurate price, stock, warehouse and variant ids for auto-ordering);
    everything else is parsed from the public product page's structured data.
    """
    supplier = detect_supplier(url)
    if supplier == "cj":
        if not (cj or settings.cj_enabled):
            raise ValueError("CJdropshipping import needs CJ_API_KEY")
        client = cj or CJClient.from_settings(settings, http=http)
        pid = cj_product_id(url)
        if not pid:
            raise ValueError(f"No CJ product id in {url}")
        return client.get_product(pid, ship_to=settings.ship_to_country, url=url if url.startswith("http") else "")
    if supplier == "aliexpress" and (ali or settings.aliexpress_enabled):
        client = ali or AliExpressClient.from_settings(settings, http=http)
        product_id = aliexpress_product_id(url)
        if product_id:
            return client.get_product(product_id, url=url, ship_to=settings.ship_to_country)
    product = fetch_product_page(url, proxy=settings.scraper_proxy or None, http=http)
    return product.model_copy(update={"supplier": supplier})


__all__ = ["detect_supplier", "import_product", "AliExpressClient", "CJClient", "fetch_product_page"]
