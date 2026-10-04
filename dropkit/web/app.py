"""Local web dashboard. Binds to 127.0.0.1 by default and has no login: do not expose it publicly."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import pricing
from ..config import Settings
from ..engine import Engine

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="dropkit")
    eng = engine or Engine(Settings.from_env())
    flash: list[str] = []

    def back(msg: str) -> RedirectResponse:
        flash.append(msg)
        return RedirectResponse("/", status_code=303)

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
        messages = list(flash)
        flash.clear()
        return TEMPLATES.TemplateResponse(request, "index.html", {
            "settings": eng.s, "listings": listings, "orders": orders, "events": eng.db.events(30), "stats": stats,
            "messages": messages, "ebay_connected": bool(eng.db.get_token("user_refresh")),
        })

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
