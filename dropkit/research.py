"""Render research reports."""

from __future__ import annotations

from datetime import date
from urllib.parse import quote_plus

from .models import ResearchReport

EBAY_DOMAINS = {"EBAY_US": "ebay.com", "EBAY_GB": "ebay.co.uk", "EBAY_FR": "ebay.fr", "EBAY_DE": "ebay.de"}


def sold_search_url(marketplace: str, query: str) -> str:
    domain = EBAY_DOMAINS.get(marketplace, "ebay.com")
    return f"https://www.{domain}/sch/i.html?_nkw={quote_plus(query)}&LH_Sold=1&LH_Complete=1"


def render_report(report: ResearchReport) -> str:
    lines = [f"# Product research - {date.today().isoformat()}", "",
             f"Marketplace: {report.marketplace} | Niche: {report.niche}", ""]
    for i, idea in enumerate(report.ideas, 1):
        lines += [
            f"## {i}. {idea.name}",
            "",
            f"- Why it sells: {idea.why_it_sells}",
            f"- Target sale price: {idea.target_sale_price:.2f} | est. supplier cost: {idea.est_supplier_cost:.2f} | est. margin: {idea.est_margin_pct:.0f}%",
            f"- VeRO risk: {idea.vero_risk}",
            f"- Verify demand (sold listings): [{idea.verify_search}]({sold_search_url(report.marketplace, idea.verify_search)})",
            f"- Find supplier: `{idea.supplier_search}` (AliExpress: filter 'Ships from' = your marketplace country)",
        ]
        if idea.sources:
            lines.append("- Sources: " + ", ".join(f"<{u}>" for u in idea.sources[:6]))
        lines.append("")
    if report.notes:
        lines += ["## Notes", "", report.notes, ""]
    lines += ["---", "Estimates are unverified. Check sold listings (>=10 sales in 30 days) and the supplier before listing.", ""]
    return "\n".join(lines)
