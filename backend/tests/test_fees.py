"""Cost-model unit tests — hand-computed against the Zerodha equity schedule.

Pure functions, no DB. Numbers cross-checked with Zerodha's public brokerage
calculator for a 100-share ₹1000→₹1100 round trip.
"""

from decimal import Decimal

import pytest
from app.trading.fees import (
    leg_charges,
    product_for_classification,
    roundtrip_charges,
)


def test_product_mapping():
    assert product_for_classification("swing") == "delivery"
    assert product_for_classification("positional") == "delivery"
    assert product_for_classification("intraday") == "intraday"
    assert product_for_classification("scalp") == "intraday"


def test_delivery_buy_leg_hand_computed():
    """BUY 100 @ ₹1000 delivery: STT 100, txn 2.97, sebi 0.10, gst 0.5526,
    stamp 15 → 118.6226 → 118.62."""
    b = leg_charges(side="BUY", product="delivery", price=Decimal("1000"), qty=100)
    assert b.brokerage == Decimal("0")
    assert b.stt == Decimal("100.000")
    assert b.stamp_duty == Decimal("15.000")
    assert b.total == Decimal("118.62")


def test_delivery_sell_leg_no_stamp():
    """SELL 100 @ ₹1100 delivery: no stamp (buy-only); STT 110 → 113.98."""
    s = leg_charges(side="SELL", product="delivery", price=Decimal("1100"), qty=100)
    assert s.stamp_duty == Decimal("0")
    assert s.stt == Decimal("110.000")
    assert s.total == Decimal("113.98")


def test_delivery_roundtrip_total():
    total, breakdown = roundtrip_charges(
        position_side="LONG",
        entry_price=Decimal("1000"),
        exit_price=Decimal("1100"),
        quantity=100,
        product="delivery",
    )
    assert total == Decimal("232.60")  # 118.62 + 113.98
    assert breakdown["entry"]["side"] == "BUY"
    assert breakdown["exit"]["side"] == "SELL"
    assert breakdown["product"] == "delivery"


def test_intraday_roundtrip_brokerage_capped_and_stt_sell_only():
    """Intraday brokerage caps at ₹20/order; STT (0.025%) hits SELL only.
    Entry 30.22 + exit 55.08 = 85.30."""
    total, breakdown = roundtrip_charges(
        position_side="LONG",
        entry_price=Decimal("1000"),
        exit_price=Decimal("1100"),
        quantity=100,
        product="intraday",
    )
    assert total == Decimal("85.30")
    # brokerage capped at 20 (0.03% of 100k = 30 → capped)
    assert breakdown["entry"]["brokerage"] == "20"
    # STT is sell-only intraday: entry buy leg has none
    assert breakdown["entry"]["stt"] == "0"


def test_short_roundtrip_mirrors_long_sides():
    """A SHORT enters with a SELL and exits with a BUY — sides mirror."""
    _total, breakdown = roundtrip_charges(
        position_side="SHORT",
        entry_price=Decimal("1100"),
        exit_price=Decimal("1000"),
        quantity=100,
        product="delivery",
    )
    assert breakdown["entry"]["side"] == "SELL"
    assert breakdown["exit"]["side"] == "BUY"
    # stamp duty is charged on the BUY leg (the exit, here)
    assert breakdown["exit"]["stamp_duty"] != "0"
    assert breakdown["entry"]["stamp_duty"] == "0"


def test_charges_scale_with_turnover():
    small = leg_charges(side="BUY", product="delivery", price=Decimal("100"), qty=10)
    big = leg_charges(side="BUY", product="delivery", price=Decimal("100"), qty=1000)
    assert big.total > small.total > Decimal("0")


def test_unknown_product_raises():
    with pytest.raises(ValueError, match="Unknown product"):
        leg_charges(side="BUY", product="futures", price=Decimal("100"), qty=1)
