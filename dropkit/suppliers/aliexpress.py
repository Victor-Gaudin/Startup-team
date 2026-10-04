"""AliExpress Open Platform - Dropshipping API client.

Official API (requires a dropshipping app at https://openservice.aliexpress.com).
Signing and method names follow the platform docs, cross-checked against the
open-source moh3a/ae_sdk client:
  sign = HMAC-SHA256(app_secret, concat(sorted(key + value))).hex().upper()
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx

from ..models import SupplierProduct

API_URL = "https://api-sg.aliexpress.com/sync"

_PRODUCT_ID = re.compile(r"/item/(?:[^/]*/)?(\d{6,})\.html|productId=(\d{6,})|/(\d{10,})\.html")


class AliExpressError(RuntimeError):
    pass


def aliexpress_product_id(url: str) -> str | None:
    m = _PRODUCT_ID.search(url)
    return next((g for g in m.groups() if g), None) if m else None


def sign(params: dict[str, Any], secret: str) -> str:
    base = "".join(f"{k}{params[k]}" for k in sorted(params) if params[k] is not None)
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def _unwrap_list(value: Any, *inner_keys: str) -> list:
    """The API wraps arrays as {"<singular>": [...]} unless simplify=true; accept both."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in inner_keys:
            if isinstance(value.get(key), list):
                return value[key]
        for v in value.values():
            if isinstance(v, list):
                return v
    return []


def _response_body(data: dict) -> dict:
    if "error_response" in data:
        err = data["error_response"]
        raise AliExpressError(f"{err.get('code')}: {err.get('msg')} ({err.get('sub_msg', '')})")
    for key, value in data.items():
        if key.endswith("_response") and isinstance(value, dict):
            return value
    return data


def sku_attr(sku: dict) -> str:
    props = _unwrap_list(sku.get("aeop_s_k_u_propertys") or sku.get("ae_sku_property_dtos"),
                         "aeop_sku_property", "ae_sku_property_d_t_o")
    parts = []
    for p in props:
        part = f"{p.get('sku_property_id')}:{p.get('property_value_id') or p.get('property_value_id_long')}"
        if p.get("property_value_definition_name"):
            part += f"#{p['property_value_definition_name']}"
        parts.append(part)
    return ";".join(parts)


@dataclass
class PlacedOrder:
    ok: bool
    order_ids: list[str]
    error: str = ""


@dataclass
class AliExpressClient:
    app_key: str
    app_secret: str
    access_token: str
    http: httpx.Client | None = None
    target_currency: str = "USD"
    target_language: str = "EN"

    @classmethod
    def from_settings(cls, settings, http: httpx.Client | None = None) -> "AliExpressClient":
        return cls(settings.aliexpress_app_key, settings.aliexpress_app_secret, settings.aliexpress_access_token, http=http)

    def call(self, method: str, **params: Any) -> dict:
        payload: dict[str, Any] = {
            "method": method,
            "app_key": self.app_key,
            "session": self.access_token,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "sha256",
            "simplify": "true",
            **{k: (json.dumps(v, separators=(",", ":")) if isinstance(v, (dict, list)) else str(v)) for k, v in params.items()},
        }
        payload["sign"] = sign(payload, self.app_secret)
        client = self.http or httpx.Client(timeout=30)
        try:
            resp = client.post(API_URL, data=payload)
        finally:
            if self.http is None:
                client.close()
        if resp.status_code >= 400:
            raise AliExpressError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return _response_body(resp.json())

    # --- products -----------------------------------------------------
    def get_product(self, product_id: str, *, url: str = "", ship_to: str = "US", sku_id: str | None = None) -> SupplierProduct:
        body = self.call(
            "aliexpress.ds.product.get",
            product_id=product_id,
            ship_to_country=ship_to,
            target_currency=self.target_currency,
            target_language=self.target_language,
        )
        result = body.get("result") or {}
        base = result.get("ae_item_base_info_dto") or {}
        skus = _unwrap_list(result.get("ae_item_sku_info_dtos"), "ae_item_sku_info_d_t_o")
        if not base or not skus:
            raise AliExpressError(f"Product {product_id} not available: {body.get('rsp_msg', 'empty result')}")

        def stock(s: dict) -> int:
            return int(s.get("sku_available_stock") or s.get("s_k_u_available_stock") or s.get("ipm_sku_stock") or 0)

        def price(s: dict) -> float:
            return float(s.get("offer_sale_price") or s.get("sku_price") or 0)

        chosen = None
        if sku_id:
            chosen = next((s for s in skus if str(s.get("sku_id") or s.get("id")) == str(sku_id)), None)
        if chosen is None:
            in_stock = [s for s in skus if stock(s) > 0] or skus
            chosen = min(in_stock, key=price)

        images = [u for u in (result.get("ae_multimedia_info_dto") or {}).get("image_urls", "").split(";") if u]
        props = _unwrap_list(result.get("ae_item_properties"), "ae_item_property")
        attributes = {str(p.get("attr_name")): str(p.get("attr_value")) for p in props if p.get("attr_name")}
        attributes["sku_attr"] = sku_attr(chosen)
        logistics = result.get("logistics_info_dto") or {}
        store = result.get("ae_store_info") or {}
        if store:
            attributes["store_name"] = str(store.get("store_name", ""))
            attributes["store_shipping_rating"] = str(store.get("shipping_speed_rating", ""))
        if base.get("avg_evaluation_rating"):
            attributes["rating"] = str(base["avg_evaluation_rating"])
            attributes["reviews"] = str(base.get("evaluation_count", ""))

        return SupplierProduct(
            supplier="aliexpress",
            url=url or f"https://www.aliexpress.com/item/{product_id}.html",
            supplier_sku=f"{product_id}:{chosen.get('sku_id') or chosen.get('id')}",
            title=str(base.get("subject", "")),
            description=re.sub(r"<[^>]+>", " ", str(base.get("detail") or ""))[:5000],
            price=price(chosen),
            currency=str(chosen.get("currency_code") or self.target_currency),
            in_stock=stock(chosen) > 0,
            stock_qty=stock(chosen),
            images=images,
            brand=attributes.get("Brand Name", ""),
            attributes=attributes,
            shipping_days=int(logistics["delivery_time"]) if str(logistics.get("delivery_time", "")).isdigit() else None,
        )

    # --- orders -------------------------------------------------------
    def place_order(self, *, product_id: str, sku_attr_value: str, quantity: int, address: dict, memo: str = "") -> PlacedOrder:
        """Create a dropshipping order. Payment is completed in the AliExpress account (auto-pay if enabled there)."""
        request = {
            "logistics_address": address,
            "product_items": [
                {
                    "product_id": int(product_id),
                    "product_count": quantity,
                    "sku_attr": sku_attr_value,
                    "order_memo": memo or "Dropship order - no invoice or promotional material please",
                }
            ],
        }
        body = self.call("aliexpress.ds.order.create", param_place_order_request4_open_api_d_t_o=request)
        result = body.get("result") or {}
        if str(result.get("is_success")).lower() == "true":
            ids = [str(x) for x in _unwrap_list(result.get("order_list"), "number")]
            return PlacedOrder(True, ids)
        return PlacedOrder(False, [], f"{result.get('error_code', 'UNKNOWN')}: {result.get('error_msg', '')}")

    def order_tracking(self, order_id: str) -> tuple[str, str] | None:
        """Return (tracking_number, carrier) once the supplier has shipped, else None."""
        body = self.call("aliexpress.trade.ds.order.get", single_order_query={"order_id": order_id})
        result = body.get("result") or {}
        infos = _unwrap_list(result.get("logistics_info_list"), "ae_order_logistics_info")
        for info in infos:
            if info.get("logistics_no"):
                return str(info["logistics_no"]), str(info.get("logistics_service") or "Other")
        return None


def ebay_address_to_aliexpress(ship_to: dict) -> dict:
    """Map an eBay Fulfillment API shipTo object to an AliExpress logistics_address."""
    contact = ship_to.get("contactAddress") or {}
    phone = (ship_to.get("primaryPhone") or {}).get("phoneNumber", "")
    return {
        "full_name": ship_to.get("fullName", ""),
        "contact_person": ship_to.get("fullName", ""),
        "address": contact.get("addressLine1", ""),
        "address2": contact.get("addressLine2", ""),
        "city": contact.get("city", ""),
        "province": contact.get("stateOrProvince", ""),
        "zip": contact.get("postalCode", ""),
        "country": contact.get("countryCode", ""),
        "mobile_no": re.sub(r"\D", "", phone)[-10:] if phone else "",
        "phone_country": "+1" if contact.get("countryCode") == "US" else "",
    }
