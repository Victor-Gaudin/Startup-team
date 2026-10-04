"""Command-line interface: `dropkit --help`."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import typer

from . import pricing
from .config import Settings
from .engine import Engine

app = typer.Typer(help="Self-hosted eBay listing automation (import, AI listings, pricing, publish, orders, monitoring).",
                  no_args_is_help=True)


def _engine() -> Engine:
    return Engine(Settings.from_env())


def _out(msg: str = "") -> None:
    typer.echo(msg)


@app.command()
def status() -> None:
    """Show configuration and counts."""
    s = Settings.from_env()
    e = Engine(s)
    _out(f"Marketplace:   {s.marketplace} ({s.ebay_env})")
    _out(f"Claude model:  {s.model}")
    _out(f"eBay app:      {'configured' if s.ebay_enabled else 'MISSING (EBAY_CLIENT_ID/SECRET)'}")
    _out(f"eBay account:  {'connected' if e.db.get_token('user_refresh') else 'not connected (dropkit ebay-connect)'}")
    _out(f"AliExpress:    {'API configured (auto-order on)' if s.aliexpress_enabled else 'page import only (no auto-order)'}")
    _out(f"Policies:      {'set' if all([s.fulfillment_policy_id, s.payment_policy_id, s.return_policy_id]) else 'MISSING (dropkit ebay-policies)'}")
    _out(f"Margin:        target {s.target_margin:.0%}, minimum {s.min_margin:.0%}, promoted {s.promoted_rate:.0%}")
    counts = {}
    for row in e.db.listings():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    _out(f"Listings:      {counts or 'none'}")
    _out(f"Orders:        {len(e.db.orders())} total, {len(e.db.orders('manual'))} need manual ordering")


# --- eBay account -------------------------------------------------------
@app.command("ebay-connect")
def ebay_connect() -> None:
    """Print the eBay consent URL to authorize this app on your seller account."""
    e = _engine()
    if not e.ebay:
        raise typer.Exit("Set EBAY_CLIENT_ID, EBAY_CLIENT_SECRET and EBAY_RU_NAME in .env first")
    _out("1. Open this URL, sign in to eBay and accept:\n")
    _out(e.ebay.consent_url())
    _out("\n2. Copy the full URL you are redirected to (or just the code) and run:\n   dropkit ebay-code '<url or code>'")


@app.command("ebay-code")
def ebay_code(code_or_url: str) -> None:
    """Finish eBay authorization with the redirect URL or code."""
    e = _engine()
    code = code_or_url
    if code_or_url.startswith("http"):
        code = parse_qs(urlparse(code_or_url).query).get("code", [""])[0]
    if not code:
        raise typer.Exit("No authorization code found")
    e.ebay.exchange_code(code)
    _out("eBay account connected.")


@app.command("ebay-policies")
def ebay_policies() -> None:
    """List your business policies (put the IDs in .env)."""
    e = _engine()
    for kind, items in e.ebay.policies().items():
        _out(f"{kind}:")
        for p in items:
            _out(f"  {p['id']}  {p['name']}")
        if not items:
            _out("  (none - create one in Seller Hub > Account > Business policies)")


@app.command("ebay-location")
def ebay_location(city: str, state: str, postal_code: str, country: str = "US") -> None:
    """Create the inventory location eBay requires before publishing."""
    e = _engine()
    e.ebay.ensure_location(e.s.merchant_location_key, city=city, state=state, postal_code=postal_code, country=country)
    _out(f"Location '{e.s.merchant_location_key}' ready.")


# --- products -----------------------------------------------------------
@app.command("import")
def import_cmd(urls: list[str]) -> None:
    """Import product(s) from AliExpress, Amazon, Cdiscount or any shop URL."""
    e = _engine()
    for url in urls:
        try:
            sku = e.import_url(url)
            _, p = e._product(sku)
            _out(f"{sku}  {p.price:.2f} {p.currency}  {'in stock' if p.in_stock else 'OUT OF STOCK'}  {p.title[:70]}")
        except Exception as exc:
            _out(f"FAILED {url}: {exc}")


@app.command("import-csv")
def import_csv(path: Path, supplier: str = "csv") -> None:
    """Import products from a wholesale supplier CSV feed."""
    from .suppliers.csv_feed import read_feed

    e = _engine()
    for product in read_feed(path, supplier=supplier):
        _out(f"{e.add_product(product)}  {product.price:.2f}  {product.title[:70]}")


@app.command()
def prepare(skus: list[str], notes: str = "", price: float = typer.Option(None, help="Override sale price")) -> None:
    """Generate AI title/description, price for target margin, run VeRO and competition checks."""
    e = _engine()
    if skus == ["all"]:
        skus = [r["sku"] for r in e.db.listings("draft")]
    for sku in skus:
        try:
            r = e.prepare(sku, notes=notes, price=price)
        except Exception as exc:
            _out(f"{sku}: FAILED {exc}")
            continue
        _out(f"\n{sku}  [{r.vero.risk.upper()} VeRO risk]")
        _out(f"  Title ({len(r.content.title)}): {r.content.title}")
        m = r.margin
        _out(f"  Price {r.price:.2f} | fees {m.final_value_fee + m.per_order_fee:.2f} | promo {m.promoted_fee:.2f} | "
             f"cost {m.cost:.2f} | profit {m.profit:.2f} ({m.margin:.0%})")
        for reason in r.vero.reasons:
            _out(f"  VeRO: {reason}")
        for w in r.warnings:
            _out(f"  ! {w}")


@app.command()
def margin(cost: float, shipping: float = 0.0, price: float = typer.Option(None), marketplace: str = typer.Option(None)) -> None:
    """Quick calculator: suggested price for target margin, or margin at a given price."""
    s = Settings.from_env()
    mp = marketplace or s.marketplace
    suggested = pricing.price_for_margin(cost, shipping, target_margin=s.target_margin, marketplace=mp,
                                         promoted_rate=s.promoted_rate, fx_rate=s.fx_rate)
    at = price or suggested
    m = pricing.margin(at, cost, shipping, marketplace=mp, promoted_rate=s.promoted_rate, fx_rate=s.fx_rate)
    _out(f"Suggested price for {s.target_margin:.0%} margin: {suggested:.2f} {pricing.fees_for(mp).currency}")
    _out(json.dumps(m.as_dict(), indent=2))


@app.command("set-price")
def set_price(sku: str, price: float) -> None:
    e = _engine()
    e.db.update_listing(sku, price=price)
    listing = e.db.listing(sku)
    if listing["status"] == "published" and e.ebay:
        e.ebay.update_price_quantity(sku, listing["offer_id"], price=price)
    _out(f"{sku} price set to {price:.2f}")


@app.command("set-category")
def set_category(sku: str, category_id: str) -> None:
    _engine().db.update_listing(sku, category_id=category_id)
    _out(f"{sku} category set to {category_id}")


@app.command()
def publish(skus: list[str]) -> None:
    """Publish prepared listing(s) to eBay. Use 'all' for every prepared draft."""
    e = _engine()
    if skus == ["all"]:
        skus = [r["sku"] for r in e.db.listings("draft") if r["content"]]
    for sku in skus:
        try:
            _out(f"{sku}: live as eBay item {e.publish(sku)}")
        except Exception as exc:
            _out(f"{sku}: FAILED {exc}")


@app.command("list")
def list_cmd(status_filter: str = typer.Option(None, "--status")) -> None:
    """Show listings."""
    e = _engine()
    for row in e.db.listings(status_filter):
        title = json.loads(row["content"])["title"] if row["content"] else "(not prepared)"
        price = f"{row['price']:.2f}" if row["price"] else "-"
        _out(f"{row['sku']}  {row['status']:<9} {price:>8}  {row['ebay_listing_id'] or '':<14} {title[:60]}")


# --- orders -------------------------------------------------------------
@app.command()
def orders(sync: bool = typer.Option(True, help="Pull new eBay orders first"), auto_order: bool = True) -> None:
    """Sync eBay orders, auto-order from AliExpress where possible, push tracking, list what needs you."""
    e = _engine()
    if sync:
        _out(f"Sync: {e.sync_orders(auto_order=auto_order)}")
    for row in e.db.orders():
        if row["status"] in ("shipped", "cancelled"):
            continue
        _out(f"{row['ebay_order_id']}  {row['status']:<8} {row['sku']} x{row['quantity']}  {row['sale_total']:.2f}  {row['note'] or ''}")


@app.command()
def ship(order_key: str, tracking_number: str, carrier: str) -> None:
    """Upload tracking for a manually ordered sale (ORDER_KEY as shown by `dropkit orders`)."""
    _engine().add_tracking(order_key, tracking_number, carrier)
    _out("Tracking uploaded; order marked shipped on eBay.")


@app.command()
def monitor() -> None:
    """Re-check supplier prices/stock and reprice or pause listings to protect margin."""
    for action in _engine().monitor() or ["no changes"]:
        _out(action)


@app.command()
def run(interval_minutes: int = 30) -> None:
    """Run order sync + monitoring forever (use a process manager or cron instead in production)."""
    e = _engine()
    while True:
        try:
            _out(f"[{time.strftime('%H:%M')}] orders {e.sync_orders()}")
            for a in e.monitor():
                _out(f"[{time.strftime('%H:%M')}] {a}")
        except Exception as exc:
            _out(f"[{time.strftime('%H:%M')}] error: {exc}")
            e.db.log("error", f"run loop: {exc}")
        time.sleep(interval_minutes * 60)


# --- research -----------------------------------------------------------
@app.command()
def research(niche: str = "phone and gaming accessories", count: int = 1, out_dir: Path = Path("research")) -> None:
    """Find fast-selling product ideas with Claude + web search; writes a markdown report."""
    from .ai import Researcher
    from .research import render_report

    s = Settings.from_env()
    e = Engine(s)
    existing = [json.loads(r["content"])["title"] for r in e.db.listings() if r["content"]]
    report = Researcher(model=s.model).run(s.marketplace, niche, count, exclude=existing)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{date.today().isoformat()}.md"
    path.write_text(render_report(report))
    _out(path.read_text())
    _out(f"\nSaved to {path}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the web dashboard."""
    import uvicorn

    from .web.app import create_app

    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    app()
