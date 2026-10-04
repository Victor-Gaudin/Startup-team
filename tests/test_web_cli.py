from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dropkit.cli import app as cli_app
from dropkit.engine import Engine
from dropkit.models import SupplierProduct
from dropkit.web.app import create_app


def test_dashboard_renders_and_actions(settings, db):
    eng = Engine(settings, db, ebay=None, ali=None)
    eng.ebay = eng.ali = eng.cj = None
    eng.add_product(SupplierProduct(supplier="generic", url="https://shop/p1", title="Cable Organizer <Kit>", price=3.0))
    client = TestClient(create_app(eng))

    page = client.get("/")
    assert page.status_code == 200
    assert "DK-00001" in page.text and "Cable Organizer &lt;Kit&gt;" in page.text  # escaped

    r = client.post("/margin", data={"cost": "5", "shipping": "1"}, follow_redirects=True)
    assert "sell at" in r.text

    r = client.post("/publish/DK-00001", follow_redirects=True)
    assert "publish failed" in r.text  # no eBay configured -> clear error, no crash

    r = client.post("/price/DK-00001", data={"price": "12.99"}, follow_redirects=True)
    assert "price set to 12.99" in r.text and db.listing("DK-00001")["price"] == 12.99


def test_cli_margin_and_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DROPKIT_DB", str(tmp_path / "cli.db"))
    runner = CliRunner()
    r = runner.invoke(cli_app, ["margin", "5", "--shipping", "1"])
    assert r.exit_code == 0 and "Suggested price" in r.output and '"margin"' in r.output
    r = runner.invoke(cli_app, ["status"])
    assert r.exit_code == 0 and "Marketplace" in r.output
    r = runner.invoke(cli_app, ["import-csv", "missing.csv"])
    assert r.exit_code != 0


def test_dashboard_verify_flow(settings, db):
    eng = Engine(settings, db, ebay=None, ali=None, cj=None)
    eng.ebay = eng.ali = eng.cj = None  # offline: no eBay/supplier lookups
    client = TestClient(create_app(eng))

    r = client.post("/verify", data={"name": "Magnetic car phone mount", "supplier_cost": "4", "supplier_shipping": "2",
                                     "delivery_days": "6", "sold_30d": "180", "active_listings": "600", "market_median": "$16.50",
                                     "sale_price": "16.99"}, follow_redirects=True)
    assert r.status_code == 200 and "score 89/100 - List it" in r.text and "/month profit" in r.text
    assert "LH_Sold=1" in r.text and "Re-score" in r.text

    check_id = db.checks()[0]["id"]
    r = client.post("/verify", data={"check_id": str(check_id), "name": "Magnetic car phone mount", "supplier_cost": "4",
                                     "supplier_shipping": "2", "sold_30d": "5"}, follow_redirects=True)
    assert "score 50/100" in r.text
    assert len(db.checks()) == 1 and db.checks()[0]["score"] < 89  # re-scored in place

    r = client.post("/verify", data={"name": "No cost"}, follow_redirects=True)
    assert "Verification failed" in r.text

    r = client.post("/candidates/load", follow_redirects=True)
    # "Magnetic car phone mount" is already verified, so its research duplicate is skipped
    assert "Loaded 14 research candidates" in r.text and len(db.checks()) == 15

    r = client.post("/suppliers", data={"query": "magnetic mount"}, follow_redirects=True)
    assert "CJ_API_KEY" in r.text and "shipFromCountry=US" in r.text

    r = client.post(f"/verify/{check_id}/delete", follow_redirects=True)
    assert len(db.checks()) == 14
