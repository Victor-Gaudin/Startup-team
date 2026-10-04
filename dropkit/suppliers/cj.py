"""CJdropshipping API 2.0 client (official API, US/EU warehouses, auto-order).

Endpoints and field names follow CJ's API 2.0 docs, cross-checked against the
open-source thayronarrais/cjdropshipping-php SDK. Responses use the envelope
{"code": 200, "result": true, "message": "...", "data": ...}.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx2 as httpx

from ..models import SupplierOffer, SupplierProduct
from .aliexpress import PlacedOrder

BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1/"

_PID = re.compile(r"-p-([0-9A-Fa-f-]{32,36})\.html|[?&]pid=([0-9A-Fa-f-]{32,36})|^cj:([0-9A-Za-z-]+)$")


class CJError(RuntimeError):
    pass


def cj_product_id(url: str) -> str | None:
    m = _PID.search(url)
    return next((g for g in m.groups() if g), None) if m else None


def parse_aging(aging: Any) -> tuple[int | None, int | None]:
    """'3-7' -> (3, 7); '7' -> (7, 7); None -> (None, None)."""
    nums = [int(n) for n in re.findall(r"\d+", str(aging or ""))]
    if not nums:
        return None, None
    return min(nums), max(nums)


def _price(value: Any) -> float:
    """CJ prices can be numbers or ranges like '2.50-3.10' (take the low end)."""
    nums = re.findall(r"\d+(?:\.\d+)?", str(value or ""))
    return float(nums[0]) if nums else 0.0


def _images(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = [v for v in value.split(",") if v]
    return [v for v in (value or []) if isinstance(v, str) and v.startswith("http")]


@dataclass
class CJClient:
    api_key: str
    db: Any = None  # dropkit.db.DB for token caching (optional)
    http: httpx.Client | None = None
    _token: tuple[str, float] | None = field(default=None, repr=False)

    @classmethod
    def from_settings(cls, settings, db=None, http: httpx.Client | None = None) -> "CJClient":
        return cls(settings.cj_api_key, db=db, http=http)

    def _http(self) -> httpx.Client:
        if self.http is None:
            self.http = httpx.Client(timeout=30)
        return self.http

    # --- auth ---------------------------------------------------------
    def access_token(self) -> str:
        now = time.time()
        if self._token and self._token[1] > now:
            return self._token[0]
        if self.db is not None:
            cached = self.db.get_token("cj_access")
            if cached and cached[1] and cached[1] > now:
                self._token = (cached[0], cached[1])
                return cached[0]
        data = self._send("POST", "authentication/getAccessToken", body={"apiKey": self.api_key}, auth=False)
        token = data["accessToken"]
        try:
            expires = datetime.fromisoformat(str(data.get("accessTokenExpiryDate"))).timestamp() - 3600
        except ValueError:
            expires = now + 14 * 86400
        self._token = (token, expires)
        if self.db is not None:
            self.db.set_token("cj_access", token, expires)
        return token

    def _send(self, method: str, path: str, *, params: dict | None = None, body: Any = None, auth: bool = True) -> Any:
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["CJ-Access-Token"] = self.access_token()
        for attempt in range(3):
            resp = self._http().request(method, BASE_URL + path, params=params, json=body, headers=headers)
            if resp.status_code == 429 and attempt < 2:
                time.sleep(1.5 * (attempt + 1))  # CJ allows ~1 request/second on most endpoints
                continue
            break
        try:
            envelope = resp.json()
        except ValueError as exc:
            raise CJError(f"CJ {path}: HTTP {resp.status_code}, invalid JSON") from exc
        code = envelope.get("code")
        ok = resp.status_code == 200 and (code in (None, 200, "200") or envelope.get("result") is True)
        if not ok:
            raise CJError(f"CJ {path}: {code} {envelope.get('message', '')}".strip())
        return envelope.get("data")

    # --- products -----------------------------------------------------
    def search(self, keyword: str, *, ship_to: str = "US", local_only: bool = False, size: int = 10) -> list[dict]:
        """Raw product summaries. local_only restricts to products stocked in a `ship_to` warehouse."""
        params: dict[str, Any] = {"keyWord": keyword, "page": 1, "size": size}
        if local_only:
            params["countryCode"] = ship_to
        data = self._send("GET", "product/listV2", params=params) or {}
        items = []
        for group in data.get("content") or []:
            items.extend(group.get("productList") or [])
        return items

    def variant_stock(self, vid: str) -> dict[str, int]:
        """Stock per warehouse country, e.g. {'US': 120, 'CN': 5000}."""
        out: dict[str, int] = {}
        for inv in self._send("GET", "product/stock/queryByVid", params={"vid": vid}) or []:
            cc = str(inv.get("countryCode") or "").upper()
            if cc:
                out[cc] = out.get(cc, 0) + int(inv.get("totalInventoryNum") or inv.get("storageNum") or 0)
        return out

    def freight(self, vid: str, *, start: str, end: str, quantity: int = 1) -> list[dict]:
        data = self._send("POST", "logistic/freightCalculate",
                          body={"startCountryCode": start, "endCountryCode": end, "products": [{"vid": vid, "quantity": quantity}]})
        options = []
        for opt in data or []:
            if not opt.get("logisticName"):
                continue
            lo, hi = parse_aging(opt.get("logisticAging"))
            options.append({"name": opt["logisticName"], "price": _price(opt.get("logisticPrice")), "days_min": lo, "days_max": hi})
        return options

    @staticmethod
    def best_option(options: list[dict]) -> dict | None:
        """Fastest option costing at most $3 more than the cheapest one."""
        if not options:
            return None
        cheapest = min(o["price"] for o in options)
        affordable = [o for o in options if o["price"] <= cheapest + 3]
        return min(affordable, key=lambda o: (o["days_max"] if o["days_max"] is not None else 99, o["price"]))

    def get_product(self, pid: str, *, ship_to: str = "US", vid: str | None = None, url: str = "") -> SupplierProduct:
        data = self._send("GET", "product/query", params={"pid": pid})
        if not data:
            raise CJError(f"CJ product {pid} not found")
        variants = data.get("variants") or []
        if not variants:
            raise CJError(f"CJ product {pid} has no variants")
        variant = next((v for v in variants if v.get("vid") == vid), None) if vid else None
        variant = variant or min(variants, key=lambda v: _price(v.get("variantSellPrice")) or 1e9)

        stock = self.variant_stock(variant["vid"])
        ships_from = ship_to if stock.get(ship_to, 0) > 0 else ("CN" if stock.get("CN", 0) > 0 else next(iter(stock), "CN"))
        option = self.best_option(self.freight(variant["vid"], start=ships_from, end=ship_to))

        description = re.sub(r"<[^>]+>", " ", str(data.get("description") or ""))
        attributes = {"vid": variant["vid"], "variant": str(variant.get("variantNameEn") or variant.get("variantKey") or "")}
        if data.get("productWeight"):
            attributes["weight_g"] = str(data["productWeight"])
        return SupplierProduct(
            supplier="cj",
            url=url or f"https://cjdropshipping.com/product/-p-{pid}.html",
            supplier_sku=f"{pid}:{variant['vid']}",
            title=str(data.get("productNameEn") or ""),
            description=re.sub(r"\s+", " ", description).strip()[:5000],
            price=_price(variant.get("variantSellPrice") or data.get("sellPrice")),
            shipping_cost=option["price"] if option else 0.0,
            currency="USD",
            in_stock=stock.get(ships_from, 0) > 0,
            stock_qty=stock.get(ships_from, 0),
            images=_images(data.get("productImageSet")) or _images([data.get("productImage") or data.get("bigImage")]),
            attributes=attributes,
            shipping_days=option["days_max"] if option else None,
            ships_from=ships_from,
            shipping_method=option["name"] if option else "",
        )

    def offers(self, keyword: str, *, ship_to: str = "US", limit: int = 4) -> list[SupplierOffer]:
        """Sourcing options for a keyword: local-warehouse products first, then the rest."""
        seen: set[str] = set()
        summaries: list[tuple[dict, bool]] = []
        for local in (True, False):
            try:
                for item in self.search(keyword, ship_to=ship_to, local_only=local, size=limit):
                    pid = str(item.get("id") or item.get("pid") or "")
                    if pid and pid not in seen:
                        seen.add(pid)
                        summaries.append((item, local))
            except CJError:
                continue
        offers: list[SupplierOffer] = []
        for item, _local in summaries[: limit * 2]:
            pid = str(item.get("id") or item.get("pid"))
            try:
                p = self.get_product(pid, ship_to=ship_to)
            except CJError as exc:
                offers.append(SupplierOffer(supplier="cj", title=str(item.get("nameEn", "")), url=f"https://cjdropshipping.com/product/-p-{pid}.html",
                                            product_id=pid, price=_price(item.get("sellPrice")), image=str(item.get("bigImage", "")),
                                            auto_order=True, note=f"details unavailable: {exc}"))
                continue
            offers.append(SupplierOffer(
                supplier="cj", title=p.title, url=p.url, product_id=pid, variant_id=p.attributes.get("vid", ""), price=p.price,
                shipping_cost=p.shipping_cost, shipping_days_max=p.shipping_days, ships_from=p.ships_from,
                shipping_method=p.shipping_method, stock=p.stock_qty, image=p.images[0] if p.images else str(item.get("bigImage", "")),
                auto_order=True,
            ))
        return offers

    # --- orders -------------------------------------------------------
    def place_order(self, product: SupplierProduct, *, quantity: int, ship_to: dict, order_number: str) -> PlacedOrder:
        """Create a CJ order from an eBay shipTo object. Pay it from your CJ balance (auto-pay can be enabled in CJ)."""
        contact = ship_to.get("contactAddress") or {}
        vid = product.attributes.get("vid") or product.supplier_sku.partition(":")[2]
        body = {
            "orderNumber": order_number,
            "shippingCountryCode": contact.get("countryCode", ""),
            "shippingCountry": contact.get("countryCode", ""),
            "shippingProvince": contact.get("stateOrProvince", ""),
            "shippingCity": contact.get("city", ""),
            "shippingAddress": contact.get("addressLine1", ""),
            "shippingAddress2": contact.get("addressLine2", ""),
            "shippingZip": contact.get("postalCode", ""),
            "shippingCustomerName": ship_to.get("fullName", ""),
            "shippingPhone": (ship_to.get("primaryPhone") or {}).get("phoneNumber", "") or "0000000000",
            "email": ship_to.get("email", ""),
            "remark": "Dropship order - no invoice or promotional material please",
            "logisticName": product.shipping_method,
            "fromCountryCode": product.ships_from or "CN",
            "products": [{"vid": vid, "quantity": quantity}],
        }
        if not body["logisticName"]:
            return PlacedOrder(False, [], "no shipping method known for this product; re-import it")
        try:
            data = self._send("POST", "shopping/order/createOrderV2", body=body)
        except CJError as exc:
            return PlacedOrder(False, [], str(exc))
        order_id = str((data or {}).get("orderId") or (data or {}).get("id") or "")
        return PlacedOrder(bool(order_id), [order_id] if order_id else [], "" if order_id else "CJ returned no order id")

    def order_tracking(self, order_id: str) -> tuple[str, str] | None:
        data = self._send("GET", "shopping/order/getOrderDetail", params={"orderId": order_id}) or {}
        number = data.get("trackNumber") or data.get("trackingNumber")
        if number:
            return str(number), str(data.get("logisticName") or "Other")
        return None
