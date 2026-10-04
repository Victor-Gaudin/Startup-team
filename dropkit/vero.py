"""Brand / VeRO (Verified Rights Owner) risk screening.

eBay removes listings and can restrict accounts when a rights owner reports
them. Unbranded products described as "compatible with <Brand>" are generally
fine; listings that look like the brand's own product are not. This module
flags risky text before anything is published.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Brands that actively enforce on eBay (non-exhaustive; extend as needed).
PROTECTED_BRANDS = {
    "apple", "iphone", "ipad", "airpods", "macbook", "magsafe", "nintendo", "switch 2", "pokemon", "sony",
    "playstation", "ps5", "ps4", "dualsense", "xbox", "microsoft", "samsung", "galaxy", "google", "pixel",
    "nike", "adidas", "jordan", "puma", "gucci", "louis vuitton", "chanel", "prada", "hermes", "rolex",
    "cartier", "dyson", "lego", "disney", "marvel", "star wars", "otterbox", "spigen", "anker", "bose",
    "beats", "jbl", "gopro", "canon", "nikon", "dji", "oakley", "ray-ban", "ugg", "north face", "carhartt",
    "levi's", "stanley", "yeti", "hydro flask", "tesla", "ferrari", "lamborghini", "harley-davidson",
    "michael kors", "coach", "tiffany", "pandora", "swarovski", "barbie", "hot wheels", "nerf", "crocs",
    "steam deck", "valve", "oral-b", "philips", "loreal", "l'oreal", "olaplex",
}

# Words that imply the item is an authentic branded / official product.
AUTHENTICITY_CLAIMS = {"genuine", "original", "authentic", "official", "oem", "licensed"}

# Words eBay or rights owners treat as counterfeit signals.
COUNTERFEIT_SIGNALS = {"replica", "inspired by", "dupe", "fake", "knockoff", "knock-off", "1:1", "aaa quality"}

COMPATIBLE_PREFIX = r"(?:compatible with|for use with|designed for|fits|for)"


@dataclass
class VeroResult:
    risk: str  # "low" | "medium" | "high"
    brands: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.risk == "high"


def _find_terms(text: str, terms: set[str]) -> list[str]:
    lowered = text.lower()
    found = []
    for term in sorted(terms):
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered):
            found.append(term)
    return found


def _is_compatibility_mention(title: str, brand: str) -> bool:
    """True when every occurrence of `brand` follows a compatibility phrase within two words."""
    lowered = title.lower()
    occurrences = list(re.finditer(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", lowered))
    for occ in occurrences:
        before = lowered[: occ.start()]
        if not re.search(rf"\b{COMPATIBLE_PREFIX}\s+(?:[\w'-]+\s+){{0,2}}$", before):
            return False
    return bool(occurrences)


def check(title: str, description: str = "", brand: str = "") -> VeroResult:
    text = f"{title}\n{description}"
    reasons: list[str] = []
    brands = _find_terms(text, PROTECTED_BRANDS)
    if brand and brand.lower() in PROTECTED_BRANDS:
        return VeroResult("high", sorted(set(brands) | {brand.lower()}),
                          [f"supplier lists the product itself as brand '{brand}'; sell only with proof of authenticity"])

    claims = _find_terms(text, AUTHENTICITY_CLAIMS)
    fakes = _find_terms(text, COUNTERFEIT_SIGNALS)

    if fakes:
        reasons.append(f"counterfeit wording: {', '.join(fakes)}")
        return VeroResult("high", brands, reasons)

    if not brands:
        return VeroResult("low", [], [])

    if claims:
        reasons.append(f"authenticity claim ({', '.join(claims)}) next to protected brand ({', '.join(brands)})")
        return VeroResult("high", brands, reasons)

    bare = [b for b in _find_terms(title, PROTECTED_BRANDS) if not _is_compatibility_mention(title, b)]
    if bare:
        reasons.append(f"brand in title not framed as compatibility ('for' / 'compatible with'): {', '.join(bare)}")
        return VeroResult("high", brands, reasons)

    reasons.append(f"mentions protected brand(s) as compatibility: {', '.join(brands)}")
    return VeroResult("medium", brands, reasons)
