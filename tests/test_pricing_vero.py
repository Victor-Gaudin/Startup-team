import pytest

from dropkit import pricing, vero


def test_margin_breakdown_us():
    m = pricing.margin(25.0, 10.0, 2.0, marketplace="EBAY_US", promoted_rate=0.04)
    assert m.final_value_fee == pytest.approx(3.40)
    assert m.per_order_fee == 0.40
    assert m.promoted_fee == pytest.approx(1.00)
    assert m.profit == pytest.approx(25 - 3.40 - 0.40 - 1.00 - 12)
    assert m.margin == pytest.approx(m.profit / 25)


@pytest.mark.parametrize("cost,ship", [(1.5, 0), (4, 1), (8.5, 0), (12, 3), (40, 0)])
@pytest.mark.parametrize("mp", ["EBAY_US", "EBAY_GB", "EBAY_FR", "EBAY_DE"])
def test_price_for_margin_hits_target(cost, ship, mp):
    price = pricing.price_for_margin(cost, ship, target_margin=0.2, marketplace=mp, promoted_rate=0.04)
    assert f"{price:.2f}".endswith(".99")
    assert pricing.margin(price, cost, ship, marketplace=mp, promoted_rate=0.04).margin >= 0.2 - 1e-9
    # one dollar lower would be below target (price is close to minimal)
    assert pricing.margin(price - 1, cost, ship, marketplace=mp, promoted_rate=0.04).margin < 0.2


def test_charm_and_errors():
    assert pricing.charm(12.10) == 12.99
    assert pricing.charm(12.99) == 12.99
    assert pricing.charm(13.0) == 13.99
    with pytest.raises(ValueError):
        pricing.price_for_margin(5, target_margin=0.9)
    with pytest.raises(ValueError):
        pricing.fees_for("EBAY_XX")


def test_fx_rate_applied():
    m = pricing.margin(20, 10, 0, marketplace="EBAY_GB", fx_rate=0.8)
    assert m.cost == pytest.approx(8.0)


@pytest.mark.parametrize(
    "title,desc,brand,risk",
    [
        ("Magnetic Car Phone Mount 360 Rotation Dashboard Holder", "", "", "low"),
        ("Clear Case Compatible with iPhone 17 Pro Shockproof", "", "", "medium"),
        ("Protective Case for Nintendo Switch 2 Hard Shell", "", "", "medium"),
        ("iPhone 17 Pro Clear Case", "", "", "high"),
        ("Genuine Apple MagSafe Charger", "", "", "high"),
        ("Wireless Earbuds Bluetooth 5.3", "AirPods replica quality", "", "high"),
        ("Bluetooth Speaker Waterproof", "", "JBL", "high"),
        ("Bluetooth Speaker Waterproof", "", "Unbranded", "low"),
        ("Phone Stand", "Works great, applesauce not included", "", "low"),
    ],
)
def test_vero(title, desc, brand, risk):
    assert vero.check(title, desc, brand).risk == risk
