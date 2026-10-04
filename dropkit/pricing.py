"""eBay fee model, margin calculation and target-margin pricing.

Fee numbers are approximations of eBay's standard rates for business sellers in
"most categories" and change over time. Override them per category with
`FeeSchedule(...)` if your category differs (e.g. some electronics/parts).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FeeSchedule:
    currency: str
    final_value_rate: float  # share of total sale amount (item + shipping charged)
    per_order_fee_low: float  # fixed fee when order total <= threshold
    per_order_fee_high: float  # fixed fee when order total > threshold
    threshold: float = 10.0

    def per_order_fee(self, total: float) -> float:
        return self.per_order_fee_high if total > self.threshold else self.per_order_fee_low


FEES: dict[str, FeeSchedule] = {
    "EBAY_US": FeeSchedule("USD", 0.136, 0.30, 0.40),
    "EBAY_GB": FeeSchedule("GBP", 0.128, 0.30, 0.30),
    "EBAY_FR": FeeSchedule("EUR", 0.117, 0.35, 0.35),
    "EBAY_DE": FeeSchedule("EUR", 0.110, 0.35, 0.35),
}


@dataclass(frozen=True)
class MarginBreakdown:
    sale_price: float
    final_value_fee: float
    per_order_fee: float
    promoted_fee: float
    cost: float
    profit: float
    margin: float  # profit / sale_price

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 2) if k != "margin" else round(v, 4) for k, v in self.__dict__.items()}


def fees_for(marketplace: str) -> FeeSchedule:
    try:
        return FEES[marketplace]
    except KeyError as exc:
        raise ValueError(f"Unsupported marketplace {marketplace!r}; known: {', '.join(FEES)}") from exc


def margin(
    sale_price: float,
    supplier_cost: float,
    supplier_shipping: float = 0.0,
    *,
    marketplace: str = "EBAY_US",
    promoted_rate: float = 0.0,
    fx_rate: float = 1.0,
    fees: FeeSchedule | None = None,
) -> MarginBreakdown:
    """Profit for one unit sold at `sale_price` (buyer pays free shipping included in price)."""
    f = fees or fees_for(marketplace)
    cost = (supplier_cost + supplier_shipping) * fx_rate
    fvf = sale_price * f.final_value_rate
    fixed = f.per_order_fee(sale_price)
    promo = sale_price * promoted_rate
    profit = sale_price - fvf - fixed - promo - cost
    return MarginBreakdown(
        sale_price=sale_price,
        final_value_fee=fvf,
        per_order_fee=fixed,
        promoted_fee=promo,
        cost=cost,
        profit=profit,
        margin=profit / sale_price if sale_price else 0.0,
    )


def charm(price: float) -> float:
    """Round up to the next .99 ending (12.10 -> 12.99, 12.99 -> 12.99)."""
    candidate = math.floor(price) + 0.99
    if candidate + 1e-9 < price:
        candidate += 1
    return round(candidate, 2)


def price_for_margin(
    supplier_cost: float,
    supplier_shipping: float = 0.0,
    *,
    target_margin: float = 0.20,
    marketplace: str = "EBAY_US",
    promoted_rate: float = 0.0,
    fx_rate: float = 1.0,
    fees: FeeSchedule | None = None,
    round_charm: bool = True,
) -> float:
    """Lowest sale price that yields at least `target_margin` net margin."""
    f = fees or fees_for(marketplace)
    variable = f.final_value_rate + promoted_rate + target_margin
    if variable >= 1:
        raise ValueError("Fees + promoted rate + target margin must be below 100%")
    cost = (supplier_cost + supplier_shipping) * fx_rate
    price = (cost + f.per_order_fee_low) / (1 - variable)
    if price > f.threshold:
        price = (cost + f.per_order_fee_high) / (1 - variable)
    return charm(price) if round_charm else round(price, 2)
