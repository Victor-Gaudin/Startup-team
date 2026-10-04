from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dropkit.cli import app as cli_app
from dropkit.engine import Engine
from dropkit.models import SupplierProduct
from dropkit.web.app import create_app


def test_dashboard_renders_and_actions(settings, db):
    eng = Engine(settings, db, ebay=None, ali=None)
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
