"""Product verification: a 0-100 score and an estimated monthly revenue.

The score is a transparent weighted sum. Every component shows its points and
the reason, so you can see why a product scored what it did. The revenue model
is deliberately simple and shown as a low / expected / high range:

    your units per month = market sales per month x your share
    your share = competition share x price factor x delivery factor
    competition share = 0.6 / sqrt(active listings), capped at 15%

Inputs you don't know can be left blank. They score neutral and lower the
confidence of the result.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from . import pricing, vero


@dataclass
class CheckInput:
    name: str
    supplier_cost: float
    supplier_shipping: float = 0.0
    sale_price: float | None = None  # leave empty to use the target-margin price
    delivery_days: int | None = None  # supplier -> buyer, worst case
    sold_30d: int | None = None  # eBay sold listings in the last 30 days for this exact product type
    active_listings: int | None = None  # competing active listings
    market_median: float | None = None  # median competitor price incl. shipping
    title: str = ""  # planned listing title, for the VeRO check (defaults to name)
    brand: str = ""
    supplier: str = ""
    supplier_url: str = ""
    keywords: str = ""  # eBay search to check demand (defaults to name)


@dataclass
class Component:
    name: str
    points: float
    max_points: int
    note: str


@dataclass
class ScoreResult:
    score: int
    verdict: str
    confidence: str
    price: float
    unit_profit: float
    margin: float
    components: list[Component]
    units: tuple[float, float, float] | None  # low, expected, high per month
    revenue: tuple[float, float, float] | None
    profit: tuple[float, float, float] | None
    warnings: list[str] = field(default_factory=list)
    vero_risk: str = "low"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["components"] = [asdict(c) for c in self.components]
        return d


def _interp(x: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation over sorted (x, y) points, clamped at the ends."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def competition_share(active_listings: int | None) -> float:
    """Share of monthly market sales a new, well-priced listing can expect."""
    if active_listings is None:
        return 0.03
    # Sales concentrate on the top listings, so share falls with sqrt(competition), not linearly:
    # 25 active -> 12%, 100 -> 6%, 400 -> 3%, 1600 -> 1.5%.
    return min(0.15, 0.6 / math.sqrt(max(active_listings, 1)))


def price_factor(price: float, median: float | None) -> float:
    if not median:
        return 1.0
    ratio = price / median
    return _interp(ratio, [(0.85, 1.4), (0.97, 1.3), (1.05, 1.0), (1.15, 0.6), (1.3, 0.25)])


def delivery_factor(days: int | None) -> float:
    if days is None:
        return 0.9
    return _interp(days, [(4, 1.25), (6, 1.1), (8, 1.0), (12, 0.7), (20, 0.4), (30, 0.2)])


def evaluate(inp: CheckInput, *, marketplace: str = "EBAY_US", promoted_rate: float = 0.04, fx_rate: float = 1.0,
             target_margin: float = 0.20, min_margin: float = 0.10) -> ScoreResult:
    warnings: list[str] = []
    price = inp.sale_price or pricing.price_for_margin(
        inp.supplier_cost, inp.supplier_shipping, target_margin=target_margin, marketplace=marketplace,
        promoted_rate=promoted_rate, fx_rate=fx_rate)
    m = pricing.margin(price, inp.supplier_cost, inp.supplier_shipping, marketplace=marketplace,
                       promoted_rate=promoted_rate, fx_rate=fx_rate)
    components: list[Component] = []

    # Demand (30)
    if inp.sold_30d is None:
        components.append(Component("Demand", 12, 30, "unknown - open the sold-listings link and enter the 30-day count"))
    else:
        pts = _interp(math.log10(inp.sold_30d + 1), [(0, 0), (1.04, 12), (1.49, 20), (2.0, 26), (2.48, 30)])
        components.append(Component("Demand", pts, 30, f"{inp.sold_30d} sold in 30 days"))
        if inp.sold_30d < 10:
            warnings.append("fewer than 10 sales in 30 days: demand is too thin to rely on")

    # Margin (25)
    pts = _interp(m.margin, [(0.05, 0), (0.10, 5), (0.15, 10), (0.20, 15), (0.30, 22), (0.40, 25)])
    components.append(Component("Margin", pts, 25, f"{m.margin:.0%} net ({m.profit:.2f} per sale at {price:.2f})"))

    # Competition / sell-through (15)
    if inp.active_listings is None or inp.sold_30d is None:
        components.append(Component("Competition", 7, 15, "unknown - enter the number of active listings"))
    else:
        str_ratio = inp.sold_30d / max(inp.active_listings, 1)
        pts = _interp(str_ratio, [(0.02, 0), (0.05, 2), (0.2, 6), (0.5, 11), (1.0, 15)])
        components.append(Component("Competition", pts, 15, f"sell-through {str_ratio:.0%} ({inp.sold_30d} sold / {inp.active_listings} active)"))

    # Price position (10)
    if inp.market_median:
        ratio = price / inp.market_median
        pts = _interp(ratio, [(1.0, 10), (1.1, 7), (1.25, 3), (1.4, 0)])
        components.append(Component("Price vs market", pts, 10, f"{price:.2f} vs median {inp.market_median:.2f} ({ratio - 1:+.0%})"))
        if ratio > 1.15:
            warnings.append("your price is well above the market: lower it or skip")
    else:
        components.append(Component("Price vs market", 5, 10, "unknown - enter the typical sold price"))

    # Delivery (10)
    if inp.delivery_days is None:
        components.append(Component("Delivery speed", 4, 10, "unknown - check the supplier's delivery estimate"))
    else:
        pts = _interp(inp.delivery_days, [(5, 10), (8, 8), (12, 5), (20, 2), (30, 0)])
        components.append(Component("Delivery speed", pts, 10, f"~{inp.delivery_days} days to the buyer"))
        if inp.delivery_days > 12:
            warnings.append("delivery over 12 days: expect cancellations and 'item not received' cases")

    # Risk (10)
    v = vero.check(inp.title or inp.name, "", inp.brand)
    risk_pts = {"low": 10, "medium": 6, "high": 0}[v.risk]
    risk_notes = [f"VeRO {v.risk}"]
    if price < 12:
        risk_pts -= 3
        risk_notes.append("low price: fixed fees eat the margin")
    components.append(Component("Risk", max(0, risk_pts), 10, "; ".join(risk_notes + v.reasons)))

    score = round(sum(c.points for c in components))
    if v.blocked:
        verdict = "Skip - brand/counterfeit risk"
        warnings.append("high VeRO risk: listing would be blocked")
    elif m.margin < min_margin:
        verdict = "Skip - margin too thin"
    elif inp.sold_30d is None:
        verdict = "Check demand first"
    elif score >= 70:
        verdict = "List it"
    elif score >= 50:
        verdict = "Test with one listing"
    else:
        verdict = "Skip"

    known = sum(x is not None for x in (inp.sold_30d, inp.active_listings, inp.market_median, inp.delivery_days))
    confidence = "high" if known == 4 else "medium" if inp.sold_30d is not None and known >= 2 else "low"

    units = revenue = profit = None
    if inp.sold_30d is not None:
        share = competition_share(inp.active_listings) * price_factor(price, inp.market_median) * delivery_factor(inp.delivery_days)
        expected = inp.sold_30d * share
        units = (round(expected * 0.5, 1), round(expected, 1), round(expected * 2, 1))
        revenue = tuple(round(u * price, 2) for u in units)
        profit = tuple(round(u * m.profit, 2) for u in units)

    return ScoreResult(score=score, verdict=verdict, confidence=confidence, price=price, unit_profit=round(m.profit, 2),
                       margin=round(m.margin, 4), components=components, units=units, revenue=revenue, profit=profit,
                       warnings=warnings, vero_risk=v.risk)
