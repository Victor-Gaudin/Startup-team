"""Settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments. Existing env vars win."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text().splitlines():
        line = raw.split(" #", 1)[0].strip() if " #" in raw else raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _f(name: str, default: float) -> float:
    value = os.environ.get(name, "")
    return float(value) if value else default


def _s(name: str, default: str = "") -> str:
    return os.environ.get(name, "") or default


@dataclass
class Settings:
    model: str = "claude-opus-5-5"

    ebay_env: str = "sandbox"
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_ru_name: str = ""
    marketplace: str = "EBAY_US"
    merchant_location_key: str = "default"
    fulfillment_policy_id: str = ""
    payment_policy_id: str = ""
    return_policy_id: str = ""

    aliexpress_app_key: str = ""
    aliexpress_app_secret: str = ""
    aliexpress_access_token: str = ""
    cj_api_key: str = ""

    target_margin: float = 0.20
    min_margin: float = 0.10
    promoted_rate: float = 0.04
    fx_rate: float = 1.0

    scraper_proxy: str = ""
    db_path: str = "dropkit.db"

    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, dotenv: str | Path | None = ".env") -> "Settings":
        if dotenv:
            load_dotenv(dotenv)
        return cls(
            model=_s("DROPKIT_MODEL", "claude-opus-5-5"),
            ebay_env=_s("EBAY_ENV", "sandbox"),
            ebay_client_id=_s("EBAY_CLIENT_ID"),
            ebay_client_secret=_s("EBAY_CLIENT_SECRET"),
            ebay_ru_name=_s("EBAY_RU_NAME"),
            marketplace=_s("EBAY_MARKETPLACE", "EBAY_US"),
            merchant_location_key=_s("EBAY_MERCHANT_LOCATION_KEY", "default"),
            fulfillment_policy_id=_s("EBAY_FULFILLMENT_POLICY_ID"),
            payment_policy_id=_s("EBAY_PAYMENT_POLICY_ID"),
            return_policy_id=_s("EBAY_RETURN_POLICY_ID"),
            aliexpress_app_key=_s("ALIEXPRESS_APP_KEY"),
            aliexpress_app_secret=_s("ALIEXPRESS_APP_SECRET"),
            aliexpress_access_token=_s("ALIEXPRESS_ACCESS_TOKEN"),
            cj_api_key=_s("CJ_API_KEY"),
            target_margin=_f("DROPKIT_TARGET_MARGIN", 0.20),
            min_margin=_f("DROPKIT_MIN_MARGIN", 0.10),
            promoted_rate=_f("DROPKIT_PROMOTED_RATE", 0.04),
            fx_rate=_f("DROPKIT_FX_RATE", 1.0),
            scraper_proxy=_s("DROPKIT_SCRAPER_PROXY"),
            db_path=_s("DROPKIT_DB", "dropkit.db"),
        )

    @property
    def aliexpress_enabled(self) -> bool:
        return bool(self.aliexpress_app_key and self.aliexpress_app_secret and self.aliexpress_access_token)

    @property
    def cj_enabled(self) -> bool:
        return bool(self.cj_api_key)

    @property
    def ship_to_country(self) -> str:
        return {"EBAY_US": "US", "EBAY_GB": "GB", "EBAY_FR": "FR", "EBAY_DE": "DE"}.get(self.marketplace, "US")

    @property
    def ebay_enabled(self) -> bool:
        return bool(self.ebay_client_id and self.ebay_client_secret)
