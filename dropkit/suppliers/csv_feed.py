"""Import products from a wholesale supplier's CSV feed.

Wholesale / dropship-program suppliers (rather than retail marketplaces) are the
sourcing model eBay's dropshipping policy allows. Expected columns (header row,
extra columns ignored): url, title, price, shipping_cost, currency, stock,
images (| separated), brand, sku, gtin, shipping_days, description
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import SupplierProduct


def read_feed(path: str | Path, supplier: str = "csv") -> list[SupplierProduct]:
    products: list[SupplierProduct] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not row.get("title") or not row.get("price"):
                raise ValueError(f"{path}:{i}: 'title' and 'price' are required")
            stock = row.get("stock", "")
            products.append(
                SupplierProduct(
                    supplier=supplier,
                    url=row.get("url") or f"csv://{Path(path).name}/{row.get('sku') or i}",
                    supplier_sku=row.get("sku", ""),
                    title=row["title"],
                    description=row.get("description", ""),
                    price=float(row["price"]),
                    shipping_cost=float(row.get("shipping_cost") or 0),
                    currency=row.get("currency") or "USD",
                    in_stock=(int(stock) > 0) if stock.isdigit() else True,
                    stock_qty=int(stock) if stock.isdigit() else None,
                    images=[u for u in row.get("images", "").split("|") if u],
                    brand=row.get("brand", ""),
                    gtin=row.get("gtin", ""),
                    shipping_days=int(row["shipping_days"]) if row.get("shipping_days", "").isdigit() else None,
                )
            )
    return products
