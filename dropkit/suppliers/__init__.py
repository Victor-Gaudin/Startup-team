"""Supplier adapters: turn a product URL or feed row into a SupplierProduct, and place orders where an API allows it."""

from __future__ import annotations

from urllib.parse import urlparse

from ..config import Settings
from ..models import SupplierProduct
from .aliexpress import AliExpressClient, aliexpress_product_id
from .generic import fetch_product_page


def detect_supplier(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "aliexpress." in host:
        return "aliexpress"
    if "amazon." in host:
        return "amazon"
    if "cdiscount." in host:
        return "cdiscount"
    return "generic"


def import_product(url: str, settings: Settings, *, http=None, ali: AliExpressClient | None = None) -> SupplierProduct:
    """Import a product from any supported URL.

    AliExpress uses the official Dropshipping API when credentials are set
    (accurate price, stock and SKU ids for auto-ordering); everything else is
    parsed from the public product page's structured data.
    """
    supplier = detect_supplier(url)
    if supplier == "aliexpress" and (ali or settings.aliexpress_enabled):
        client = ali or AliExpressClient.from_settings(settings, http=http)
        product_id = aliexpress_product_id(url)
        if product_id:
            return client.get_product(product_id, url=url, ship_to=settings.marketplace[-2:])
    product = fetch_product_page(url, proxy=settings.scraper_proxy or None, http=http)
    return product.model_copy(update={"supplier": supplier})


__all__ = ["detect_supplier", "import_product", "AliExpressClient", "fetch_product_page"]
