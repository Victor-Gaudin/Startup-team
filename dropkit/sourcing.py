"""Compare suppliers for a product, fastest delivery first."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

from .models import SupplierOffer


@dataclass
class SupplierLink:
    name: str
    url: str
    note: str
    auto_order: bool = False


@dataclass
class Comparison:
    query: str
    ship_to: str
    offers: list[SupplierOffer] = field(default_factory=list)
    links: list[SupplierLink] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def search_links(query: str, ship_to: str = "US") -> list[SupplierLink]:
    """Where to look by hand, local warehouses first. Paste a product URL back into dropkit to import it."""
    q = quote_plus(query)
    links = [
        SupplierLink("CJdropshipping", f"https://www.google.com/search?q=site%3Acjdropshipping.com+{q}",
                     f"API supplier with {ship_to} warehouses (often 3-8 day delivery); auto-order with CJ_API_KEY", True),
        SupplierLink(f"AliExpress ({ship_to} warehouse)", f"https://www.aliexpress.us/w/wholesale-{q.replace('+', '-')}.html?shipFromCountry={ship_to}",
                     "Filter 'Ships from' to your country for 3-10 day delivery; auto-order with the AliExpress DS API", True),
        SupplierLink("AliExpress (all)", f"https://www.aliexpress.com/w/wholesale-{q.replace('+', '-')}.html",
                     "Cheapest, but 10-20+ days from China"),
        SupplierLink("Spocket", "https://www.spocket.co/", "US/EU suppliers, 2-7 days; order through Spocket (no public API)"),
        SupplierLink("Zendrop", "https://www.zendrop.com/", "US fulfillment centers; order through Zendrop (no public API)"),
    ]
    if ship_to == "US":
        links.append(SupplierLink("Walmart", f"https://www.walmart.com/search?q={q}",
                                  "1-3 day delivery but retail: eBay forbids buying from retailers to ship to your buyer"))
        links.append(SupplierLink("Amazon", f"https://www.amazon.com/s?k={q}",
                                  "Fast, but retail: eBay forbids it, and Amazon packaging reveals the source"))
    return links


def compare(query: str, *, ship_to: str = "US", cj=None, limit: int = 4) -> Comparison:
    result = Comparison(query=query, ship_to=ship_to, links=search_links(query, ship_to))
    if cj is not None:
        try:
            result.offers.extend(cj.offers(query, ship_to=ship_to, limit=limit))
        except Exception as exc:
            result.errors.append(f"CJdropshipping: {exc}")
    else:
        result.errors.append("CJdropshipping offers need CJ_API_KEY (live price, stock and delivery per warehouse)")

    def key(o: SupplierOffer):
        days = o.shipping_days_max if o.shipping_days_max is not None else 99
        return (days > 8, o.landed_cost if o.landed_cost is not None else o.price + 50, days)

    result.offers.sort(key=key)  # fast (<= 8 days) first, then cheapest landed cost
    return result
