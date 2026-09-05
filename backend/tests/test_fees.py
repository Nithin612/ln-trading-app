"""Cost-model unit tests — hand-computed against the Zerodha equity schedule.

Pure functions, no DB. Numbers cross-checked with Zerodha's public brokerage
calculator for a 100-share ₹1000→₹1100 round trip.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.models.signal import Signal
from app.models.trading import Position
from app.trading.fees import (
    leg_charges,
    product_for_classification,
    roundtrip_charges,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock


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
    """SELL 100 @ ₹1100 delivery: no stamp (buy-only); STT 110; DP 15.34 → 129.32.

    Was 113.98 before A29 — the flat depository charge is levied when shares leave the
    demat account, i.e. on the delivery SELL only."""
    s = leg_charges(side="SELL", product="delivery", price=Decimal("1100"), qty=100)
    assert s.stamp_duty == Decimal("0")
    assert s.stt == Decimal("110.000")
    assert s.dp_charge == Decimal("15.34")
    assert s.total == Decimal("129.32")


def test_delivery_roundtrip_total():
    total, breakdown = roundtrip_charges(
        position_side="LONG",
        entry_price=Decimal("1000"),
        exit_price=Decimal("1100"),
        quantity=100,
        product="delivery",
    )
    assert total == Decimal("247.94")  # 118.62 + 129.32 (incl. the ₹15.34 DP charge)
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


# ── A29: the flat depository charge ─────────────────────────────────────────


def test_dp_charge_is_delivery_sell_only():
    """It is levied when shares leave the demat account — so no BUY leg, and no intraday
    leg at all (nothing is delivered)."""
    assert leg_charges(
        side="SELL", product="delivery", price=Decimal("100"), qty=10
    ).dp_charge == Decimal("15.34")
    for side, product in (("BUY", "delivery"), ("BUY", "intraday"), ("SELL", "intraday")):
        assert leg_charges(
            side=side, product=product, price=Decimal("100"), qty=10
        ).dp_charge == Decimal("0"), f"{side}/{product} should carry no DP charge"


def test_dp_charge_does_not_scale_with_quantity():
    """The whole point: it is FLAT. Two legs differing only in size pay the same DP."""
    small = leg_charges(side="SELL", product="delivery", price=Decimal("100"), qty=1)
    big = leg_charges(side="SELL", product="delivery", price=Decimal("100"), qty=100_000)
    assert small.dp_charge == big.dp_charge == Decimal("15.34")


def test_a_flat_charge_costs_a_small_position_relatively_more():
    """The finding's actual claim, asserted rather than described: a fixed cost is not
    neutral to position size. It falls hardest on small positions — the shape the notional
    cap produces, and the shape live trading (₹1 lakh, 1–2 positions) will have.

    This is why omitting it under-costed the book in the direction that flatters an
    already-negative expectancy."""

    def bps(qty: int, price: str) -> Decimal:
        px = Decimal(price)
        total, _ = roundtrip_charges(
            position_side="LONG", entry_price=px, exit_price=px,
            quantity=qty, product="delivery",
        )
        return total / (px * qty) * Decimal("10000")

    tiny = bps(100, "39")        # ₹3,900 position
    large = bps(400, "2500")     # ₹10,00,000 position
    assert tiny > large * 2, f"flat cost not biting small positions: {tiny} vs {large}"


def test_the_cost_floor_is_off_by_default_and_applies_when_set():
    """Zero by default because the Zerodha schedule has no minimum — inventing one would
    fabricate a cost. The mechanism exists so a broker that DOES levy one needs no call-site
    change."""
    from dataclasses import replace

    from app.trading.fees import ZERODHA_EQUITY

    assert ZERODHA_EQUITY.min_charge_per_leg == Decimal("0")
    tiny = leg_charges(side="BUY", product="delivery", price=Decimal("1"), qty=1)
    assert tiny.total < Decimal("50")
    floored = leg_charges(
        side="BUY", product="delivery", price=Decimal("1"), qty=1,
        schedule=replace(ZERODHA_EQUITY, min_charge_per_leg=Decimal("50")),
    )
    assert floored.total == Decimal("50")


def test_the_breakdown_reports_the_dp_charge():
    """It must be visible in the audit payload, not buried in the total — a charge you
    cannot see is one nobody will notice going wrong."""
    _total, breakdown = roundtrip_charges(
        position_side="LONG", entry_price=Decimal("1000"), exit_price=Decimal("1100"),
        quantity=100, product="delivery",
    )
    assert breakdown["exit"]["dp_charge"] == "15.34"
    assert breakdown["entry"]["dp_charge"] == "0"
    # No dates passed here, so the legs record none — the back-compat path. The SEAM test
    # below is what proves a real position's own dates reach the schedule.
    assert breakdown["entry"]["priced_on"] is None


def test_unknown_product_raises():
    with pytest.raises(ValueError, match="Unknown product"):
        leg_charges(side="BUY", product="futures", price=Decimal("100"), qty=1)


# ── The SEAM: does the DP charge actually reach a closed position? ──────────
# A29 is a cost-model change, and A37 taught the lesson the hard way: a feature whose
# tests only exercise the pure function can be wired up wrong (or not at all) with a fully
# green suite. This closes a real paper position through the real broker.


async def test_a_closed_delivery_position_is_charged_the_dp_fee(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Close a swing (→ delivery) long and assert the depository charge is BOTH stored in
    `position.charges` and itemised in the closing order's audit payload.

    Canary: the arithmetic below fails on the pre-A29 model by exactly ₹15.34, and the
    payload assertion fails outright because the field did not exist."""
    from app.broker.paper_broker import close_position

    monkeypatch.setattr(settings, "paper_costs_enabled", True)

    user = await create_test_user(db, email="a29seam@example.com")
    stock = await make_stock(db, symbol="DPSEAM")
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock.id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="1000.0000", stop_loss="960.0000", take_profit="1100.0000",
        suggested_qty=100, confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "x"},
        },
        headline="BUY DPSEAM", status="active",
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=100,
        avg_entry_price=Decimal("1000"), current_sl=Decimal("960"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=now,
        signal_id=sig.id,
    )
    db.add(pos)
    await db.commit()

    order, _pos = await close_position(db, pos, exit_price=Decimal("1100"), reason="manual")
    await db.commit()

    expected, _ = roundtrip_charges(
        position_side="LONG", entry_price=Decimal("1000"),
        exit_price=Decimal(str(pos.exit_price)), quantity=100, product="delivery",
    )
    assert pos.charges == expected
    # The DP charge is inside that total, itemised on the SELL leg.
    assert order.broker_payload["charges"]["exit"]["dp_charge"] == "15.34"
    assert order.broker_payload["charges"]["entry"]["dp_charge"] == "0"
    # A23 seam: the ENTRY leg was priced on the position's OWN open date, not today's.
    assert order.broker_payload["charges"]["entry"]["priced_on"] == pos.opened_at.date().isoformat()
    assert order.broker_payload["charges"]["exit"]["priced_on"] is not None
    # And it is not free: the same trade costed without the DP fee is ₹15.34 cheaper.
    from dataclasses import replace

    from app.trading.fees import ZERODHA_EQUITY

    without, _ = roundtrip_charges(
        position_side="LONG", entry_price=Decimal("1000"),
        exit_price=Decimal(str(pos.exit_price)), quantity=100, product="delivery",
        schedule=replace(ZERODHA_EQUITY, dp_charge_per_sell=Decimal("0")),
    )
    assert expected - without == Decimal("15.34")


# ── A23: the effective-dated registry ───────────────────────────────────────


def test_schedule_history_is_ascending_and_non_empty():
    """`schedule_for` walks the list and stops at the first entry past the date, so an
    out-of-order registry would silently return the wrong schedule."""
    from app.trading.fees import SCHEDULE_HISTORY

    assert SCHEDULE_HISTORY
    dates = [e.effective_from for e in SCHEDULE_HISTORY]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates)), "two schedules cannot take effect the same day"


def test_schedule_for_returns_the_entry_in_force():
    """With a synthetic three-entry history: on the boundary date the NEW schedule applies,
    the day before it does not."""
    from dataclasses import replace as dc_replace

    from app.trading.fees import ZERODHA_EQUITY, DatedSchedule, schedule_for

    a = dc_replace(ZERODHA_EQUITY, delivery_stt_pct=Decimal("0.1"))
    b = dc_replace(ZERODHA_EQUITY, delivery_stt_pct=Decimal("0.2"))
    hist = (
        DatedSchedule(date(2020, 1, 1), a, "a"),
        DatedSchedule(date(2024, 7, 1), b, "b"),
    )

    def lookup(on: date):
        match = None
        for e in hist:
            if e.effective_from <= on:
                match = e.schedule
            else:
                break
        return match

    assert lookup(date(2024, 6, 30)).delivery_stt_pct == Decimal("0.1")
    assert lookup(date(2024, 7, 1)).delivery_stt_pct == Decimal("0.2")
    assert lookup(date(2026, 1, 1)).delivery_stt_pct == Decimal("0.2")
    # and the real registry answers for a real trade date
    assert schedule_for(date(2026, 9, 5)).dp_charge_per_sell == Decimal("15.34")


def test_a_date_before_coverage_raises_rather_than_guessing():
    """Falling back to the earliest schedule would cost a trade with rates from outside
    their period and call it a number. Unknown must be loud."""
    from app.trading.fees import SCHEDULE_HISTORY, schedule_for

    before = SCHEDULE_HISTORY[0].effective_from - timedelta(days=1)
    with pytest.raises(ValueError, match="no fee schedule covers"):
        schedule_for(before)


def test_each_leg_is_costed_on_its_own_date():
    """The point of the registry: a position opened before a rate change and closed after
    it paid TWO schedules. Uses an explicit two-entry history via the `schedule` override
    being absent and dates straddling a synthetic change."""
    from dataclasses import replace as dc_replace

    import app.trading.fees as fees_mod

    cheap = dc_replace(fees_mod.ZERODHA_EQUITY, delivery_stt_pct=Decimal("0.05"))
    dear = dc_replace(fees_mod.ZERODHA_EQUITY, delivery_stt_pct=Decimal("0.50"))
    original = fees_mod.SCHEDULE_HISTORY
    fees_mod.SCHEDULE_HISTORY = (
        fees_mod.DatedSchedule(date(2020, 1, 1), cheap, "cheap"),
        fees_mod.DatedSchedule(date(2026, 6, 1), dear, "dear"),
    )
    try:
        total, breakdown = roundtrip_charges(
            position_side="LONG", entry_price=Decimal("1000"), exit_price=Decimal("1000"),
            quantity=100, product="delivery",
            entry_on=date(2026, 5, 1),   # under `cheap`
            exit_on=date(2026, 7, 1),    # under `dear`
        )
        entry_stt = Decimal(breakdown["entry"]["stt"])
        exit_stt = Decimal(breakdown["exit"]["stt"])
        assert entry_stt == Decimal("50.000")    # 0.05% of 100,000
        assert exit_stt == Decimal("500.000")    # 0.50% of 100,000
        assert exit_stt == entry_stt * 10
        assert total > Decimal("500")
        # the record says which date priced each leg
        assert breakdown["entry"]["priced_on"] == "2026-05-01"
        assert breakdown["exit"]["priced_on"] == "2026-07-01"
    finally:
        fees_mod.SCHEDULE_HISTORY = original


def test_an_explicit_schedule_still_overrides_the_registry():
    """Tests and what-if costing pass a schedule directly; the date must then be ignored."""
    from dataclasses import replace as dc_replace

    from app.trading.fees import ZERODHA_EQUITY

    free = dc_replace(
        ZERODHA_EQUITY, delivery_stt_pct=Decimal("0"), dp_charge_per_sell=Decimal("0")
    )
    b = leg_charges(
        side="SELL", product="delivery", price=Decimal("1000"), qty=100,
        on=date(2026, 9, 5), schedule=free,
    )
    assert b.stt == Decimal("0")
    assert b.dp_charge == Decimal("0")


def test_omitting_the_date_uses_the_current_schedule():
    """Back-compat for a fill happening NOW — and the reason historical callers must pass
    `on` explicitly rather than relying on the default."""
    dated = leg_charges(
        side="SELL", product="delivery", price=Decimal("1000"), qty=100, on=date(2026, 9, 5)
    )
    undated = leg_charges(side="SELL", product="delivery", price=Decimal("1000"), qty=100)
    assert dated.total == undated.total

