"""Core data types shared across modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SupplierProduct(BaseModel):
    """A product as seen on a supplier site, normalized."""

    supplier: str  # "aliexpress" | "amazon" | "cdiscount" | "generic" | "csv"
    url: str
    supplier_sku: str = ""
    title: str
    description: str = ""
    price: float  # unit cost, supplier currency
    shipping_cost: float = 0.0
    currency: str = "USD"
    in_stock: bool = True
    stock_qty: int | None = None
    images: list[str] = Field(default_factory=list)
    brand: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    gtin: str = ""
    shipping_days: int | None = None  # supplier's estimated delivery time
    ships_from: str = ""  # ISO country of the warehouse that ships the order
    shipping_method: str = ""  # supplier logistics service used for orders


class SupplierOffer(BaseModel):
    """One sourcing option for a product, used to compare suppliers."""

    supplier: str
    title: str
    url: str
    product_id: str = ""
    variant_id: str = ""
    price: float
    shipping_cost: float | None = None
    shipping_days_min: int | None = None
    shipping_days_max: int | None = None
    ships_from: str = ""
    shipping_method: str = ""
    stock: int | None = None
    image: str = ""
    auto_order: bool = False  # can dropkit place orders with this supplier automatically
    note: str = ""

    @property
    def landed_cost(self) -> float | None:
        return None if self.shipping_cost is None else round(self.price + self.shipping_cost, 2)


class ItemSpecific(BaseModel):
    name: str
    value: str


class ListingContent(BaseModel):
    """AI-generated listing copy. Validated before it ever reaches eBay."""

    title: str = Field(description="eBay title, at most 80 characters, keyword-first, no ALL CAPS, no brand claims")
    description_html: str = Field(description="Product description as simple HTML (p, ul, li, strong, h3 only)")
    item_specifics: list[ItemSpecific] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list, description="Keywords for eBay category suggestion")
    condition: str = Field(default="NEW", description="eBay condition enum, usually NEW")


class ProductIdea(BaseModel):
    name: str
    why_it_sells: str
    target_sale_price: float
    est_supplier_cost: float
    est_margin_pct: float
    vero_risk: str = Field(description="low | medium | high")
    verify_search: str = Field(description="exact eBay search query to verify sold listings")
    supplier_search: str = Field(description="search query to find it on AliExpress / a wholesaler")
    sources: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    marketplace: str
    niche: str
    ideas: list[ProductIdea]
    notes: str = ""
