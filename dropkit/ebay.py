"""eBay REST API client (official Sell/Commerce/Buy APIs, OAuth 2.0).

Only documented endpoints are used. Requests are paced and retried on 429/5xx
to stay inside eBay's API call limits.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx2 as httpx

from .db import DB

SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
]
APP_SCOPE = "https://api.ebay.com/oauth/api_scope"

CONTENT_LANGUAGE = {"EBAY_US": "en-US", "EBAY_GB": "en-GB", "EBAY_FR": "fr-FR", "EBAY_DE": "de-DE"}
CURRENCY = {"EBAY_US": "USD", "EBAY_GB": "GBP", "EBAY_FR": "EUR", "EBAY_DE": "EUR"}


class EbayError(RuntimeError):
    def __init__(self, message: str, status: int = 0, errors: list | None = None):
        super().__init__(message)
        self.status = status
        self.errors = errors or []

    def has_error_id(self, error_id: int) -> bool:
        return any(e.get("errorId") == error_id for e in self.errors)


@dataclass
class EbayClient:
    client_id: str
    client_secret: str
    ru_name: str
    db: DB
    marketplace: str = "EBAY_US"
    sandbox: bool = True
    http: httpx.Client | None = None
    min_interval: float = 0.25  # seconds between calls (pacing, well under API limits)
    _last_call: float = field(default=0.0, repr=False)

    @classmethod
    def from_settings(cls, settings, db: DB, http: httpx.Client | None = None) -> "EbayClient":
        return cls(
            settings.ebay_client_id,
            settings.ebay_client_secret,
            settings.ebay_ru_name,
            db,
            marketplace=settings.marketplace,
            sandbox=settings.ebay_env != "production",
            http=http,
        )

    # --- hosts --------------------------------------------------------
    @property
    def api_host(self) -> str:
        return "https://api.sandbox.ebay.com" if self.sandbox else "https://api.ebay.com"

    @property
    def auth_host(self) -> str:
        return "https://auth.sandbox.ebay.com" if self.sandbox else "https://auth.ebay.com"

    @property
    def currency(self) -> str:
        return CURRENCY[self.marketplace]

    def _http(self) -> httpx.Client:
        if self.http is None:
            self.http = httpx.Client(timeout=60)
        return self.http

    # --- OAuth --------------------------------------------------------
    def consent_url(self, state: str = "dropkit") -> str:
        query = urlencode(
            {"client_id": self.client_id, "response_type": "code", "redirect_uri": self.ru_name, "scope": " ".join(SCOPES), "state": state}
        )
        return f"{self.auth_host}/oauth2/authorize?{query}"

    def _basic(self) -> str:
        return "Basic " + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

    def _token_request(self, data: dict) -> dict:
        resp = self._http().post(
            f"{self.api_host}/identity/v1/oauth2/token",
            data=data,
            headers={"Authorization": self._basic(), "Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise EbayError(f"OAuth error {resp.status_code}: {resp.text[:300]}", resp.status_code)
        return resp.json()

    def exchange_code(self, code: str) -> None:
        """Exchange the authorization code from the consent redirect for user tokens."""
        tok = self._token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": self.ru_name})
        now = time.time()
        self.db.set_token("user_access", tok["access_token"], now + int(tok.get("expires_in", 7200)) - 60)
        self.db.set_token("user_refresh", tok["refresh_token"], now + int(tok.get("refresh_token_expires_in", 47304000)))

    def user_token(self) -> str:
        cached = self.db.get_token("user_access")
        if cached and cached[1] and cached[1] > time.time():
            return cached[0]
        refresh = self.db.get_token("user_refresh")
        if not refresh:
            raise EbayError("eBay account not connected. Run `dropkit ebay-connect` first.")
        tok = self._token_request({"grant_type": "refresh_token", "refresh_token": refresh[0], "scope": " ".join(SCOPES)})
        self.db.set_token("user_access", tok["access_token"], time.time() + int(tok.get("expires_in", 7200)) - 60)
        return tok["access_token"]

    def app_token(self) -> str:
        cached = self.db.get_token("app_access")
        if cached and cached[1] and cached[1] > time.time():
            return cached[0]
        tok = self._token_request({"grant_type": "client_credentials", "scope": APP_SCOPE})
        self.db.set_token("app_access", tok["access_token"], time.time() + int(tok.get("expires_in", 7200)) - 60)
        return tok["access_token"]

    # --- core request -------------------------------------------------
    def request(self, method: str, path: str, *, user: bool = True, json: Any = None, params: dict | None = None,
                headers: dict | None = None, retries: int = 4) -> dict:
        token = self.user_token() if user else self.app_token()
        hdrs = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Language": CONTENT_LANGUAGE.get(self.marketplace, "en-US"),
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            **(headers or {}),
        }
        if json is not None:
            hdrs["Content-Type"] = "application/json"
        for attempt in range(retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self._http().request(method, f"{self.api_host}{path}", json=json, params=params, headers=hdrs)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = resp.headers.get("retry-after")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30))
                continue
            break
        if resp.status_code >= 400:
            try:
                errors = resp.json().get("errors", [])
            except ValueError:
                errors = []
            msg = "; ".join(f"{e.get('errorId')}: {e.get('message')}" for e in errors) or resp.text[:300]
            raise EbayError(f"eBay {method} {path} -> {resp.status_code}: {msg}", resp.status_code, errors)
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    # --- account / setup ----------------------------------------------
    def policies(self) -> dict[str, list[dict]]:
        out = {}
        for kind in ("fulfillment_policy", "payment_policy", "return_policy"):
            data = self.request("GET", f"/sell/account/v1/{kind}", params={"marketplace_id": self.marketplace})
            key = {"fulfillment_policy": "fulfillmentPolicies", "payment_policy": "paymentPolicies", "return_policy": "returnPolicies"}[kind]
            out[kind] = [{"id": p.get(f"{kind.split('_')[0]}PolicyId"), "name": p.get("name")} for p in data.get(key, [])]
        return out

    def ensure_location(self, key: str, *, city: str, state: str, postal_code: str, country: str) -> None:
        try:
            self.request("GET", f"/sell/inventory/v1/location/{key}")
            return
        except EbayError as exc:
            if exc.status != 404:
                raise
        self.request(
            "POST",
            f"/sell/inventory/v1/location/{key}",
            json={
                "location": {"address": {"city": city, "stateOrProvince": state, "postalCode": postal_code, "country": country}},
                "locationTypes": ["WAREHOUSE"],
                "name": "Dropkit fulfillment",
                "merchantLocationStatus": "ENABLED",
            },
        )

    # --- taxonomy -----------------------------------------------------
    def suggest_category(self, query: str) -> tuple[str, str] | None:
        tree = self.request("GET", "/commerce/taxonomy/v1/get_default_category_tree_id", user=False,
                            params={"marketplace_id": self.marketplace})
        tree_id = tree["categoryTreeId"]
        data = self.request("GET", f"/commerce/taxonomy/v1/category_tree/{tree_id}/get_category_suggestions",
                            user=False, params={"q": query})
        suggestions = data.get("categorySuggestions") or []
        if not suggestions:
            return None
        cat = suggestions[0]["category"]
        return cat["categoryId"], cat.get("categoryName", "")

    # --- inventory / offers --------------------------------------------
    def put_inventory_item(self, sku: str, *, title: str, description: str, aspects: dict[str, list[str]],
                           images: list[str], quantity: int, condition: str = "NEW", gtin: str = "") -> None:
        product: dict[str, Any] = {"title": title, "description": description, "aspects": aspects, "imageUrls": images[:24]}
        if gtin:
            product["upc" if len(gtin) == 12 else "ean"] = [gtin]
        self.request(
            "PUT",
            f"/sell/inventory/v1/inventory_item/{sku}",
            json={"availability": {"shipToLocationAvailability": {"quantity": quantity}}, "condition": condition, "product": product},
        )

    def upsert_offer(self, sku: str, *, price: float, quantity: int, category_id: str, description: str,
                     policies: dict[str, str], location_key: str) -> str:
        body = {
            "sku": sku,
            "marketplaceId": self.marketplace,
            "format": "FIXED_PRICE",
            "availableQuantity": quantity,
            "categoryId": category_id,
            "listingDescription": description,
            "listingPolicies": {
                "fulfillmentPolicyId": policies["fulfillment"],
                "paymentPolicyId": policies["payment"],
                "returnPolicyId": policies["return"],
            },
            "pricingSummary": {"price": {"value": f"{price:.2f}", "currency": self.currency}},
            "merchantLocationKey": location_key,
        }
        row = self.db.listing(sku)
        offer_id = row["offer_id"] if row and row["offer_id"] else None
        if offer_id is None:
            try:
                return self.request("POST", "/sell/inventory/v1/offer", json=body)["offerId"]
            except EbayError as exc:
                if not exc.has_error_id(25002):  # offer already exists for this SKU/marketplace
                    raise
                existing = self.request("GET", "/sell/inventory/v1/offer", params={"sku": sku, "marketplace_id": self.marketplace})
                offer_id = existing["offers"][0]["offerId"]
        self.request("PUT", f"/sell/inventory/v1/offer/{offer_id}", json=body)
        return offer_id

    def publish_offer(self, offer_id: str) -> str:
        return self.request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish")["listingId"]

    def withdraw_offer(self, offer_id: str) -> None:
        self.request("POST", f"/sell/inventory/v1/offer/{offer_id}/withdraw")

    def update_price_quantity(self, sku: str, offer_id: str, *, price: float | None = None, quantity: int | None = None) -> None:
        offer: dict[str, Any] = {"offerId": offer_id}
        req: dict[str, Any] = {"sku": sku, "offers": [offer]}
        if price is not None:
            offer["price"] = {"value": f"{price:.2f}", "currency": self.currency}
        if quantity is not None:
            offer["availableQuantity"] = quantity
            req["shipToLocationAvailability"] = {"quantity": quantity}
        data = self.request("POST", "/sell/inventory/v1/bulk_update_price_quantity", json={"requests": [req]})
        for r in data.get("responses", []):
            if int(r.get("statusCode", 200)) >= 400:
                raise EbayError(f"Price/quantity update failed for {sku}: {r.get('errors')}", int(r["statusCode"]), r.get("errors"))

    # --- orders -------------------------------------------------------
    def open_orders(self, days: int = 30) -> list[dict]:
        since = datetime.fromtimestamp(time.time() - days * 86400, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        orders: list[dict] = []
        offset = 0
        while True:
            data = self.request(
                "GET",
                "/sell/fulfillment/v1/order",
                params={"filter": f"creationdate:[{since}..],orderfulfillmentstatus:{{NOT_STARTED|IN_PROGRESS}}", "limit": 50, "offset": offset},
            )
            batch = data.get("orders", [])
            orders.extend(batch)
            if len(batch) < 50:
                return orders
            offset += 50

    def mark_shipped(self, order_id: str, line_items: list[dict], *, tracking_number: str, carrier: str) -> str:
        data = self.request(
            "POST",
            f"/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            json={
                "lineItems": [{"lineItemId": li["lineItemId"], "quantity": li.get("quantity", 1)} for li in line_items],
                "shippedDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "shippingCarrierCode": carrier,
                "trackingNumber": tracking_number,
            },
        )
        return data.get("fulfillmentId", "")

    # --- market research ----------------------------------------------
    def search_active(self, query: str, limit: int = 20) -> list[dict]:
        """Active competing listings (Browse API, app token). Returns price + shipping + title."""
        data = self.request(
            "GET", "/buy/browse/v1/item_summary/search", user=False,
            params={"q": query, "limit": limit, "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}"},
        )
        out = []
        for item in data.get("itemSummaries", []):
            price = float(item.get("price", {}).get("value", 0) or 0)
            ship_opts = item.get("shippingOptions") or [{}]
            ship = float((ship_opts[0].get("shippingCost") or {}).get("value", 0) or 0)
            out.append({"title": item.get("title", ""), "price": price, "shipping": ship, "total": round(price + ship, 2),
                        "url": item.get("itemWebUrl", ""), "seller": (item.get("seller") or {}).get("username", "")})
        return out
