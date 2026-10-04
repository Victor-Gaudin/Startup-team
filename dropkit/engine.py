"""Orchestration: import -> prepare -> publish, order sync, price/stock monitoring."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field

from . import pricing, vero
from .ai import ListingWriter
from .config import Settings
from .db import DB
from .ebay import EbayClient, EbayError
from .models import ListingContent, SupplierProduct
from .suppliers import import_product
from .suppliers.aliexpress import AliExpressClient, AliExpressError, ebay_address_to_aliexpress

CARRIERS = [("usps", "USPS"), ("ups", "UPS"), ("fedex", "FedEx"), ("dhl", "DHL"), ("royal mail", "RoyalMail"),
            ("colissimo", "Colissimo"), ("la poste", "LaPoste"), ("dpd", "DPD"), ("gls", "GLS"), ("hermes", "Hermes"),
            ("evri", "Evri"), ("yanwen", "Yanwen"), ("4px", "4PX"), ("cainiao", "Cainiao"), ("china post", "ChinaPost")]


def carrier_code(name: str) -> str:
    lowered = name.lower()
    return next((code for key, code in CARRIERS if key in lowered), "Other")


@dataclass
class PrepareResult:
    sku: str
    content: ListingContent
    price: float
    margin: pricing.MarginBreakdown
    vero: vero.VeroResult
    competitors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Engine:
    def __init__(self, settings: Settings, db: DB | None = None, *, ebay: EbayClient | None = None,
                 ali: AliExpressClient | None = None, writer: ListingWriter | None = None, http=None):
        self.s = settings
        self.db = db or DB(settings.db_path)
        self.http = http
        self.ebay = ebay or (EbayClient.from_settings(settings, self.db) if settings.ebay_enabled else None)
        self.ali = ali or (AliExpressClient.from_settings(settings) if settings.aliexpress_enabled else None)
        self._writer = writer
        self.default_quantity = 3
        self.daily_publish_limit = 20

    @property
    def writer(self) -> ListingWriter:
        if self._writer is None:
            self._writer = ListingWriter(model=self.s.model)
        return self._writer

    def _require_ebay(self) -> EbayClient:
        if not self.ebay:
            raise EbayError("eBay credentials missing: set EBAY_CLIENT_ID / EBAY_CLIENT_SECRET / EBAY_RU_NAME")
        return self.ebay

    @staticmethod
    def sku_for(product_id: int) -> str:
        return f"DK-{product_id:05d}"

    def _product(self, sku: str) -> tuple[dict, SupplierProduct]:
        listing = self.db.listing(sku)
        if not listing:
            raise KeyError(f"Unknown SKU {sku}")
        row = self.db.product(listing["product_id"])
        return dict(listing), SupplierProduct.model_validate_json(row["data"])

    # --- import -------------------------------------------------------
    def add_product(self, product: SupplierProduct) -> str:
        product_id = self.db.upsert_product(product)
        sku = self.sku_for(product_id)
        if not self.db.listing(sku):
            self.db.upsert_listing(sku=sku, product_id=product_id, marketplace=self.s.marketplace, status="draft")
        self.db.log("import", f"{sku} <- {product.supplier}: {product.title[:80]} @ {product.price} {product.currency}")
        return sku

    def import_url(self, url: str) -> str:
        return self.add_product(import_product(url, self.s, http=self.http, ali=self.ali))

    def refetch(self, product: SupplierProduct) -> SupplierProduct:
        """Fresh supplier data for an already-imported product (same variant)."""
        if product.supplier == "aliexpress" and self.ali and ":" in product.supplier_sku:
            product_id, _, sku_id = product.supplier_sku.partition(":")
            return self.ali.get_product(product_id, url=product.url, ship_to=self.s.marketplace[-2:], sku_id=sku_id or None)
        if product.supplier == "csv":
            raise ValueError("CSV products are refreshed by re-importing the feed")
        return import_product(product.url, self.s, http=self.http, ali=self.ali)

    # --- prepare ------------------------------------------------------
    def price_for(self, product: SupplierProduct) -> float:
        return pricing.price_for_margin(
            product.price, product.shipping_cost, target_margin=self.s.target_margin, marketplace=self.s.marketplace,
            promoted_rate=self.s.promoted_rate, fx_rate=self.s.fx_rate,
        )

    def margin_at(self, product: SupplierProduct, price: float) -> pricing.MarginBreakdown:
        return pricing.margin(price, product.price, product.shipping_cost, marketplace=self.s.marketplace,
                              promoted_rate=self.s.promoted_rate, fx_rate=self.s.fx_rate)

    def prepare(self, sku: str, *, notes: str = "", price: float | None = None, check_competition: bool = True) -> PrepareResult:
        listing, product = self._product(sku)
        warnings: list[str] = []

        pre = vero.check(product.title, "", product.brand)
        if pre.blocked:
            warnings.append(f"supplier title already looks branded ({'; '.join(pre.reasons)}); AI copy must avoid it")

        content = self.writer.write(product, self.s.marketplace, notes=notes)
        result = vero.check(content.title, content.description_html, product.brand)

        sale_price = price or self.price_for(product)
        breakdown = self.margin_at(product, sale_price)

        competitors: list[dict] = []
        if check_competition and self.ebay:
            try:
                query = " ".join(content.search_keywords[:1]) or content.title
                competitors = self.ebay.search_active(query)
            except EbayError as exc:
                warnings.append(f"competitor check failed: {exc}")
        if competitors:
            totals = sorted(c["total"] for c in competitors if c["total"] > 0)
            if totals:
                median = statistics.median(totals)
                if sale_price > median * 1.15:
                    warnings.append(f"price {sale_price:.2f} is >15% above market median {median:.2f}; expect slow sales")
                elif sale_price < totals[0]:
                    warnings.append(f"price {sale_price:.2f} undercuts cheapest competitor {totals[0]:.2f}; you may be leaving margin")

        if product.shipping_days and product.shipping_days > 10:
            warnings.append(f"supplier delivery ~{product.shipping_days} days; set handling/shipping policy to match")
        if not product.in_stock:
            warnings.append("supplier shows out of stock")
        if len(product.images) < 3:
            warnings.append(f"only {len(product.images)} image(s); eBay buyers expect 3+")

        if listing["status"] in ("published", "paused") and not result.blocked:
            warnings.append("listing is live: run publish again to push the new copy and price to eBay")
        status = "blocked" if result.blocked else listing["status"] if listing["status"] != "blocked" else "draft"
        self.db.upsert_listing(
            sku=sku, product_id=listing["product_id"], marketplace=self.s.marketplace, content=content.model_dump_json(),
            price=sale_price, quantity=min(self.default_quantity, product.stock_qty or self.default_quantity),
            status=status, vero_flags={"risk": result.risk, "reasons": result.reasons},
        )
        self.db.log("prepare", f"{sku}: {content.title} @ {sale_price:.2f} margin {breakdown.margin:.0%} vero={result.risk}")
        return PrepareResult(sku, content, sale_price, breakdown, result, competitors, warnings)

    # --- publish ------------------------------------------------------
    def publish(self, sku: str) -> str:
        ebay = self._require_ebay()
        listing, product = self._product(sku)
        if listing["status"] == "blocked":
            raise ValueError(f"{sku} is blocked by the VeRO check: {listing['vero_flags']}")
        if not listing["content"]:
            raise ValueError(f"{sku} has no listing copy yet; run prepare first")
        if not product.in_stock:
            raise ValueError(f"{sku}: supplier is out of stock")
        if not product.images:
            raise ValueError(f"{sku}: no images to publish")
        policies = {"fulfillment": self.s.fulfillment_policy_id, "payment": self.s.payment_policy_id, "return": self.s.return_policy_id}
        if not all(policies.values()):
            raise ValueError("Set EBAY_FULFILLMENT_POLICY_ID / EBAY_PAYMENT_POLICY_ID / EBAY_RETURN_POLICY_ID (see `dropkit ebay-policies`)")
        is_update = bool(listing["ebay_listing_id"])
        if not is_update and self.db.count_published_since(time.time() - 86400) >= self.daily_publish_limit:
            raise ValueError(f"Daily publish limit ({self.daily_publish_limit}) reached; new seller accounts have listing caps")

        content = ListingContent.model_validate_json(listing["content"])
        breakdown = self.margin_at(product, listing["price"])
        if breakdown.margin < self.s.min_margin:
            raise ValueError(f"{sku}: margin {breakdown.margin:.0%} is below the minimum {self.s.min_margin:.0%}")

        category_id = listing["category_id"]
        if not category_id:
            suggestion = ebay.suggest_category(" ".join(content.search_keywords[:3]) or content.title)
            if not suggestion:
                raise ValueError(f"{sku}: no eBay category found; set one with `dropkit set-category`")
            category_id = suggestion[0]

        aspects: dict[str, list[str]] = {}
        for spec in content.item_specifics:
            if spec.name and spec.value:
                aspects.setdefault(spec.name[:65], []).append(spec.value[:65])
        aspects.setdefault("Brand", ["Unbranded"])
        aspects.setdefault("MPN", ["Does Not Apply"])

        quantity = int(listing["quantity"] or self.default_quantity)
        ebay.put_inventory_item(sku, title=content.title, description=content.description_html, aspects=aspects,
                                images=product.images, quantity=quantity, condition=content.condition or "NEW", gtin=product.gtin)
        offer_id = ebay.upsert_offer(sku, price=listing["price"], quantity=quantity, category_id=category_id,
                                     description=content.description_html, policies=policies, location_key=self.s.merchant_location_key)
        self.db.update_listing(sku, offer_id=offer_id, category_id=category_id)
        listing_id = ebay.publish_offer(offer_id)
        self.db.update_listing(sku, ebay_listing_id=listing_id, status="published")
        self.db.log("update" if is_update else "publish", f"{sku} -> eBay item {listing_id} @ {listing['price']:.2f}")
        return listing_id

    # --- orders -------------------------------------------------------
    def sync_orders(self, *, auto_order: bool = True) -> dict[str, int]:
        ebay = self._require_ebay()
        stats = {"new": 0, "ordered": 0, "manual": 0, "shipped": 0, "errors": 0}
        for order in ebay.open_orders():
            ship_to = ((order.get("fulfillmentStartInstructions") or [{}])[0].get("shippingStep") or {}).get("shipTo") or {}
            for li in order.get("lineItems", []):
                sku = li.get("sku", "")
                if not sku.startswith("DK-"):
                    continue
                key = f"{order['orderId']}:{li['lineItemId']}"
                inserted = self.db.insert_order(
                    ebay_order_id=key, sku=sku, quantity=int(li.get("quantity", 1)),
                    sale_total=float((li.get("total") or li.get("lineItemCost") or {}).get("value", 0) or 0),
                    buyer_name=ship_to.get("fullName", ""), ship_to=json.dumps(ship_to),
                    raw=json.dumps({"orderId": order["orderId"], "lineItemId": li["lineItemId"], "quantity": li.get("quantity", 1)}),
                )
                if inserted:
                    stats["new"] += 1
                    self.db.log("order", f"New sale {key} {sku} x{li.get('quantity', 1)}")

        for row in self.db.orders("new"):
            outcome = self._fulfil(row, auto_order=auto_order)
            stats[outcome] += 1

        for row in self.db.orders("ordered"):
            if self._push_tracking(row):
                stats["shipped"] += 1
        return stats

    def _fulfil(self, row, *, auto_order: bool) -> str:
        key, sku = row["ebay_order_id"], row["sku"]
        try:
            listing, product = self._product(sku)
        except KeyError:
            self.db.update_order(key, status="error", note="SKU not found in local database")
            return "errors"

        if not (auto_order and self.ali and product.supplier == "aliexpress" and product.attributes.get("sku_attr") is not None):
            self.db.update_order(key, status="manual", note=f"Order manually: {product.url} x{row['quantity']}")
            self.db.log("order", f"{key}: manual order needed at {product.url}")
            return "manual"

        product_id = product.supplier_sku.partition(":")[0]
        try:
            fresh = self.refetch(product)
            unit_sale = row["sale_total"] / max(1, row["quantity"])
            check = self.margin_at(fresh, unit_sale)
            if not fresh.in_stock or check.margin < 0:
                reason = "out of stock" if not fresh.in_stock else f"would lose {abs(check.profit):.2f} per unit"
                self.db.update_order(key, status="manual", note=f"Auto-order skipped: {reason}. Supplier: {product.url}")
                self.db.log("order", f"{key}: auto-order skipped ({reason})")
                return "manual"
            placed = self.ali.place_order(
                product_id=product_id, sku_attr_value=fresh.attributes.get("sku_attr", ""), quantity=row["quantity"],
                address=ebay_address_to_aliexpress(json.loads(row["ship_to"] or "{}")),
            )
        except Exception as exc:  # any supplier failure falls back to a manual order, never a lost sale
            self.db.update_order(key, status="manual", note=f"Auto-order failed: {exc}")
            self.db.log("error", f"{key}: auto-order error {exc}")
            return "manual"
        if not placed.ok:
            self.db.update_order(key, status="manual", note=f"Auto-order rejected: {placed.error}")
            self.db.log("error", f"{key}: AliExpress rejected order ({placed.error})")
            return "manual"
        self.db.update_order(key, status="ordered", supplier_order_id=",".join(placed.order_ids))
        self.db.log("order", f"{key}: AliExpress order {placed.order_ids} placed (pay it in AliExpress if auto-pay is off)")
        return "ordered"

    def _push_tracking(self, row) -> bool:
        if not (self.ali and row["supplier_order_id"]):
            return False
        try:
            tracking = self.ali.order_tracking(row["supplier_order_id"].split(",")[0])
        except AliExpressError as exc:
            self.db.log("error", f"{row['ebay_order_id']}: tracking lookup failed ({exc})")
            return False
        if not tracking:
            return False
        number, carrier = tracking
        return self.add_tracking(row["ebay_order_id"], number, carrier)

    def add_tracking(self, key: str, tracking_number: str, carrier: str) -> bool:
        ebay = self._require_ebay()
        row = next((r for r in self.db.orders() if r["ebay_order_id"] == key), None)
        if row is None:
            raise KeyError(f"Unknown order {key}")
        raw = json.loads(row["raw"] or "{}")
        code = carrier_code(carrier)
        ebay.mark_shipped(raw["orderId"], [{"lineItemId": raw["lineItemId"], "quantity": raw.get("quantity", 1)}],
                          tracking_number=tracking_number, carrier=code)
        self.db.update_order(key, status="shipped", tracking_number=tracking_number, carrier=code)
        self.db.log("ship", f"{key}: tracking {tracking_number} ({code}) uploaded to eBay")
        return True

    # --- monitor ("snipe") --------------------------------------------
    def monitor(self, *, max_increase: float = 0.25) -> list[str]:
        """Re-check supplier price/stock for every live listing and protect margin.

        - out of stock -> quantity 0 (listing stays, no oversells)
        - cost moved -> reprice to target margin, unless that means a jump above
          `max_increase`, in which case the listing is paused for review
        - back in stock -> quantity restored
        """
        ebay = self._require_ebay()
        actions: list[str] = []
        for listing in self.db.listings():
            if listing["status"] not in ("published", "paused") or not listing["offer_id"]:
                continue
            sku = listing["sku"]
            _, old = self._product(sku)
            try:
                fresh = self.refetch(old)
            except Exception as exc:  # supplier page changed / blocked: keep listing, report
                actions.append(f"{sku}: supplier check failed ({exc})")
                self.db.log("error", f"monitor {sku}: {exc}")
                continue
            self.db.upsert_product(fresh)

            if not fresh.in_stock:
                if listing["status"] != "paused":
                    ebay.update_price_quantity(sku, listing["offer_id"], quantity=0)
                    self.db.update_listing(sku, status="paused", quantity=0)
                    actions.append(f"{sku}: supplier out of stock -> paused (qty 0)")
                continue

            current_price = float(listing["price"])
            target_price = self.price_for(fresh)
            current_margin = self.margin_at(fresh, current_price).margin
            new_price = None
            if current_margin < self.s.min_margin or abs(fresh.price - old.price) / max(old.price, 0.01) > 0.02:
                new_price = target_price

            if new_price and new_price > current_price * (1 + max_increase):
                if listing["status"] != "paused":
                    ebay.update_price_quantity(sku, listing["offer_id"], quantity=0)
                    self.db.update_listing(sku, status="paused", quantity=0)
                actions.append(f"{sku}: cost jumped {old.price:.2f}->{fresh.price:.2f}; needs {new_price:.2f} (> +{max_increase:.0%}) -> paused for review")
                continue

            quantity = None
            if listing["status"] == "paused":
                quantity = min(self.default_quantity, fresh.stock_qty or self.default_quantity)
            if (new_price and abs(new_price - current_price) >= 0.01) or quantity:
                ebay.update_price_quantity(sku, listing["offer_id"], price=new_price if new_price else None, quantity=quantity)
                updates: dict = {"status": "published"}
                if new_price:
                    updates["price"] = new_price
                if quantity:
                    updates["quantity"] = quantity
                self.db.update_listing(sku, **updates)
                msg = f"{sku}: "
                msg += f"repriced {current_price:.2f}->{new_price:.2f} (cost {old.price:.2f}->{fresh.price:.2f})" if new_price else ""
                msg += (" " if new_price else "") + (f"restocked qty {quantity}" if quantity else "")
                actions.append(msg)
        for a in actions:
            self.db.log("monitor", a)
        return actions
