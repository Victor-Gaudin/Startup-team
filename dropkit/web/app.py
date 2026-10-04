"""Local web dashboard. Binds to 127.0.0.1 by default and has no login: do not expose it publicly."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import pricing, scoring, sourcing
from ..config import Settings
from ..engine import Engine
from ..research import sold_search_url

CANDIDATES = Path(__file__).resolve().parents[2] / "research" / "candidates.json"


def _num(value: str | None, cast=float):
    value = (value or "").strip().replace(",", ".").lstrip("$€£")
    return cast(float(value)) if value else None

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="dropkit")
    eng = engine or Engine(Settings.from_env())
    flash: list[str] = []
    state: dict = {"comparison": None}

    def back(msg: str, anchor: str = "") -> RedirectResponse:
        flash.append(msg)
        return RedirectResponse(f"/{anchor}", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        listings = []
        for row in eng.db.listings():
            content = json.loads(row["content"]) if row["content"] else None
            vero_flags = json.loads(row["vero_flags"]) if row["vero_flags"] else {}
            product = eng.db.product(row["product_id"])
            pdata = json.loads(product["data"]) if product else {}
            m = None
            if row["price"] and pdata:
                m = pricing.margin(row["price"], pdata["price"], pdata.get("shipping_cost", 0), marketplace=eng.s.marketplace,
                                   promoted_rate=eng.s.promoted_rate, fx_rate=eng.s.fx_rate)
            listings.append({"row": row, "title": content["title"] if content else pdata.get("title", ""),
                             "vero": vero_flags.get("risk", "-"), "margin": m, "supplier_url": pdata.get("url", "")})
        orders = eng.db.orders()
        stats = {
            "published": sum(1 for x in listings if x["row"]["status"] == "published"),
            "drafts": sum(1 for x in listings if x["row"]["status"] == "draft"),
            "orders": len(orders),
            "revenue": sum(o["sale_total"] or 0 for o in orders),
            "manual": sum(1 for o in orders if o["status"] == "manual"),
        }
        checks = []
        for row in eng.db.checks():
            inp = json.loads(row["input"])
            res = json.loads(row["result"]) if row["result"] else None
            checks.append({"id": row["id"], "source": row["source"], "input": inp, "result": res,
                           "sold_url": sold_search_url(eng.s.marketplace, inp.get("keywords") or inp["name"])})
        messages = list(flash)
        flash.clear()
        return TEMPLATES.TemplateResponse(request, "index.html", {
            "settings": eng.s, "listings": listings, "orders": orders, "events": eng.db.events(30), "stats": stats,
            "messages": messages, "ebay_connected": bool(eng.db.get_token("user_refresh")), "checks": checks,
            "comparison": state["comparison"], "has_candidates": CANDIDATES.is_file(),
        })

    @app.post("/verify")
    def do_verify(name: str = Form(...), supplier_cost: str = Form(""), supplier_shipping: str = Form(""),
                  sale_price: str = Form(""), delivery_days: str = Form(""), sold_30d: str = Form(""),
                  active_listings: str = Form(""), market_median: str = Form(""), supplier_url: str = Form(""),
                  keywords: str = Form(""), title: str = Form(""), check_id: str = Form("")):
        try:
            previous = eng.db.check(int(check_id)) if check_id else None
            base = json.loads(previous["input"]) if previous else {}
            inp = scoring.CheckInput(
                name=name.strip(),
                supplier_cost=_num(supplier_cost) or 0.0,
                supplier_shipping=_num(supplier_shipping) or 0.0,
                sale_price=_num(sale_price),
                delivery_days=_num(delivery_days, int),
                sold_30d=_num(sold_30d, int),
                active_listings=_num(active_listings, int),
                market_median=_num(market_median),
                supplier_url=supplier_url.strip(),
                keywords=keywords.strip() or base.get("keywords", ""),
                title=title.strip() or base.get("title", ""),
                supplier=base.get("supplier", ""),
                brand=base.get("brand", ""),
            )
            cid, _, r = eng.verify(inp, check_id=int(check_id) if check_id else None,
                                   source=previous["source"] if previous else "manual")
        except Exception as exc:
            return back(f"Verification failed: {exc}", "#verify")
        money = ""
        if r.profit:
            money = f", est. {r.profit[1]:.0f}/month profit on {r.revenue[1]:.0f} revenue (range {r.profit[0]:.0f}-{r.profit[2]:.0f})"
        return back(f"{name}: score {r.score}/100 - {r.verdict}{money}", f"#check-{cid}")

    @app.post("/verify/{check_id}/delete")
    def do_delete_check(check_id: int):
        eng.db.delete_check(check_id)
        return back("Removed", "#verify")

    @app.post("/candidates/load")
    def do_load_candidates():
        try:
            return back(f"Loaded {eng.load_candidates(CANDIDATES)} research candidates", "#verify")
        except Exception as exc:
            return back(f"Could not load candidates: {exc}", "#verify")

    @app.post("/suppliers")
    def do_suppliers(query: str = Form(...)):
        state["comparison"] = sourcing.compare(query.strip(), ship_to=eng.s.ship_to_country, cj=eng.cj)
        found = len(state["comparison"].offers)
        return back(f"Supplier search for '{query}': {found} live offer(s)", "#suppliers")

    @app.post("/import")
    def do_import(urls: str = Form(...)):
        done = []
        for url in [u.strip() for u in urls.splitlines() if u.strip()]:
            try:
                done.append(eng.import_url(url))
            except Exception as exc:
                flash.append(f"Import failed for {url}: {exc}")
        return back(f"Imported {', '.join(done) or 'nothing'}")

    @app.post("/prepare/{sku}")
    def do_prepare(sku: str, notes: str = Form("")):
        try:
            r = eng.prepare(sku, notes=notes)
        except Exception as exc:
            return back(f"{sku}: prepare failed: {exc}")
        extra = "; ".join(r.warnings + r.vero.reasons)
        return back(f"{sku}: '{r.content.title}' @ {r.price:.2f} ({r.margin.margin:.0%} margin, VeRO {r.vero.risk}). {extra}")

    @app.post("/publish/{sku}")
    def do_publish(sku: str):
        try:
            return back(f"{sku}: live as eBay item {eng.publish(sku)}")
        except Exception as exc:
            return back(f"{sku}: publish failed: {exc}")

    @app.post("/price/{sku}")
    def do_price(sku: str, price: float = Form(...)):
        eng.db.update_listing(sku, price=price)
        row = eng.db.listing(sku)
        if row["status"] == "published" and eng.ebay:
            try:
                eng.ebay.update_price_quantity(sku, row["offer_id"], price=price)
            except Exception as exc:
                return back(f"{sku}: eBay price update failed: {exc}")
        return back(f"{sku}: price set to {price:.2f}")

    @app.post("/orders/sync")
    def do_sync():
        try:
            return back(f"Orders: {eng.sync_orders()}")
        except Exception as exc:
            return back(f"Order sync failed: {exc}")

    @app.post("/orders/{key}/ship")
    def do_ship(key: str, tracking: str = Form(...), carrier: str = Form(...)):
        try:
            eng.add_tracking(key, tracking, carrier)
            return back(f"{key}: tracking uploaded")
        except Exception as exc:
            return back(f"{key}: tracking upload failed: {exc}")

    @app.post("/monitor")
    def do_monitor():
        try:
            return back("Monitor: " + ("; ".join(eng.monitor()) or "no changes"))
        except Exception as exc:
            return back(f"Monitor failed: {exc}")

    @app.post("/margin")
    def do_margin(cost: float = Form(...), shipping: float = Form(0.0)):
        p = pricing.price_for_margin(cost, shipping, target_margin=eng.s.target_margin, marketplace=eng.s.marketplace,
                                     promoted_rate=eng.s.promoted_rate, fx_rate=eng.s.fx_rate)
        m = pricing.margin(p, cost, shipping, marketplace=eng.s.marketplace, promoted_rate=eng.s.promoted_rate, fx_rate=eng.s.fx_rate)
        return back(f"Cost {cost:.2f}+{shipping:.2f} -> sell at {p:.2f}, profit {m.profit:.2f} ({m.margin:.0%})")

    return app
