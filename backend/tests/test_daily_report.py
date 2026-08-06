"""Tests for the daily trading-analysis report generator.

Pure-function coverage (chase / oversize math and tape MFE/MAE with timing),
plus DB-integration tests through the seam that assembles a day's report —
including a regression test for the temporal look-ahead bug where a position
opened on day D but closed on D+1 was rendered as closed (with D+1's exit) in
D's report.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.market_data import Ohlcv1m
from app.models.signal import Signal
from app.models.trading import Position
from app.services.daily_report import (
    build_daily_report,
    chase_metrics,
    render_markdown,
    tape_excursion,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

# ── chase_metrics (pure) ──────────────────────────────────────────────────────


def test_chase_metrics_chased_long_is_oversized() -> None:
    """A BUY filled well past the signal entry (the BAJAJFINSV pattern): the
    position silently carries more risk than it was sized for, R:R collapses,
    and the fill is flagged past the 0.33R don't-chase ceiling."""
    c = chase_metrics(
        side="LONG",
        fill=Decimal("2104.80"),
        sig_entry=Decimal("2029.10"),
        sig_sl=Decimal("1927.60"),
        sig_tp=Decimal("2333.60"),
        quantity=20,
        capital=Decimal("100000"),
        risk_pct=Decimal("2"),
    )
    assert c.chase_r == Decimal("0.746")  # 75.70 / 101.50
    assert c.past_chase_ceiling is True
    assert c.oversize_factor == Decimal("1.746")  # 177.20 / 101.50 risk-per-share
    assert c.actual_risk_inr == Decimal("3544.00")  # 20 × 177.20
    assert c.risk_budget_multiple == Decimal("1.772")  # 3544 / (100000×2%)
    assert c.rr_designed == Decimal("3.00")
    assert c.rr_at_fill == Decimal("1.29")  # reward shrank, risk grew


def test_chase_metrics_better_fill_is_not_chasing() -> None:
    """A BUY filled BELOW the signal entry is a better-than-plan fill — negative
    chase, under 1× risk, never flagged."""
    c = chase_metrics(
        side="LONG",
        fill=Decimal("19.35"),
        sig_entry=Decimal("19.74"),
        sig_sl=Decimal("18.26"),
        sig_tp=Decimal("20.92"),
        quantity=100,
        capital=Decimal("100000"),
        risk_pct=Decimal("2"),
    )
    assert c.chase_r < 0
    assert c.past_chase_ceiling is False
    assert c.oversize_factor < Decimal("1")


def test_chase_metrics_short_direction() -> None:
    """For a SHORT, chasing = selling LOWER than the signal entry."""
    c = chase_metrics(
        side="SHORT",
        fill=Decimal("140.60"),
        sig_entry=Decimal("141.33"),
        sig_sl=Decimal("148.95"),
        sig_tp=Decimal("132.85"),
        quantity=262,
        capital=Decimal("100000"),
        risk_pct=Decimal("2"),
    )
    # chase_price = entry − fill = 0.73 ; R = 7.62 → 0.096R
    assert c.chase_r == Decimal("0.096")
    assert c.actual_risk_inr == Decimal("2187.70")  # 262 × |140.60 − 148.95|


# ── tape_excursion (pure) ─────────────────────────────────────────────────────


def _bars(
    rows: list[tuple[int, str, str, str]],
) -> list[tuple[datetime, Decimal, Decimal, Decimal]]:
    base = datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    return [
        (base + timedelta(minutes=m), Decimal(h), Decimal(lo), Decimal(cl))
        for (m, h, lo, cl) in rows
    ]


def test_tape_excursion_long_mfe_mae_timing() -> None:
    bars = _bars([(0, "102", "99", "101"), (1, "108", "101", "107"), (2, "106", "103", "104")])
    e = tape_excursion(bars, side="LONG", entry=Decimal("100"), risk=Decimal("5"), quantity=10)
    assert e is not None
    assert e.mfe_price == Decimal("108")
    assert e.mfe_time == datetime(2026, 8, 5, 4, 1, tzinfo=UTC)
    assert e.mfe_r == Decimal("1.600")
    assert e.mfe_pnl == Decimal("80.00")
    assert e.reached_1r is True
    assert e.mae_price == Decimal("99")  # min low, at bar 0
    assert e.mae_r == Decimal("-0.200")
    assert e.last_close == Decimal("104")


def test_tape_excursion_short_favourable_is_down() -> None:
    bars = _bars([(0, "101", "98", "99"), (1, "102", "95", "96"), (2, "100", "97", "98")])
    e = tape_excursion(bars, side="SHORT", entry=Decimal("100"), risk=Decimal("5"), quantity=10)
    assert e is not None
    assert e.mfe_price == Decimal("95")  # lowest low = best for a short
    assert e.mfe_r == Decimal("1.000")
    assert e.reached_1r is True
    assert e.mae_price == Decimal("102")  # highest high = worst for a short


def test_tape_excursion_empty_tape() -> None:
    assert (
        tape_excursion([], side="LONG", entry=Decimal("100"), risk=Decimal("5"), quantity=1) is None
    )


# ── DB integration ────────────────────────────────────────────────────────────


async def _signal(
    db: AsyncSession,
    stock_id: int,
    *,
    created: datetime,
    entry: str,
    sl: str,
    tp: str,
    direction: str = "BUY",
    classification: str = "positional",
) -> Signal:
    sig = Signal(
        stock_id=stock_id,
        direction=direction,
        classification=classification,
        timeframe="1d",
        entry_price=Decimal(entry),
        stop_loss=Decimal(sl),
        take_profit=Decimal(tp),
        suggested_qty=1,
        confidence_pct=76,
        factor_scores={"SR_ZONE": {"weight": 10, "score": 0.8, "explanation": "at support"}},
        headline=f"{direction} @ {entry}",
        status="active",
        validity_until=created + timedelta(days=30),
        created_at=created,
    )
    db.add(sig)
    await db.flush()
    return sig


def _candles(
    db: AsyncSession, stock_id: int, base: datetime, rows: list[tuple[int, str, str, str, str]]
) -> None:
    for m, o, h, lo, cl in rows:
        db.add(
            Ohlcv1m(
                time=base + timedelta(minutes=m),
                stock_id=stock_id,
                open=Decimal(o),
                high=Decimal(h),
                low=Decimal(lo),
                close=Decimal(cl),
                volume=1000,
                is_complete=True,
            )
        )


async def test_build_daily_report_flags_chased_open_position(db: AsyncSession) -> None:
    """End-to-end: a chased, oversized entry that pops then fades shows up with
    the right chase/oversize metrics, an MFE under +1R (lock never arms), and
    counts as open at day end."""
    now = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)  # 13:30 IST
    opened = datetime(2026, 8, 5, 4, 0, tzinfo=UTC)  # 09:30 IST
    user = await create_test_user(db, email="rep1@example.com")
    user.profit_lock_enabled = True
    stock = await make_stock(db, symbol="BAJAJFINSV")
    sig = await _signal(db, stock.id, created=opened, entry="2029.10", sl="1927.60", tp="2333.60")
    pos = Position(
        user_id=user.id,
        stock_id=stock.id,
        mode="paper",
        side="LONG",
        quantity=20,
        avg_entry_price=Decimal("2104.80"),
        current_sl=Decimal("1927.60"),
        current_tp=Decimal("2333.60"),
        trail_state="none",
        realized_pnl=Decimal("0"),
        opened_at=opened,
        signal_id=sig.id,
    )
    db.add(pos)
    # small pop to 2111.90 then fade back below the fill
    _candles(
        db,
        stock.id,
        opened,
        [
            (1, "2104", "2111.90", "2103", "2110"),
            (5, "2108", "2109", "2095", "2096"),
            (30, "2096", "2098", "2088", "2090"),
        ],
    )
    await db.commit()

    report = await build_daily_report(db, day=date(2026, 8, 5), user_id=user.id, now=now)

    assert len(report.opened) == 1
    row = report.opened[0]
    assert row.symbol == "BAJAJFINSV"
    assert row.closed_in_window is False  # still open at day end
    assert row.chase is not None and row.chase.past_chase_ceiling is True
    assert row.chase.risk_budget_multiple == Decimal("1.772")
    assert row.excursion is not None
    assert row.excursion.mfe_price == Decimal("2111.90")
    assert row.excursion.reached_1r is False  # pop was well under +1R
    # portfolio heat = the one open position's risk-at-fill
    assert report.open_risk_total == row.chase.actual_risk_inr
    assert "BAJAJFINSV" in render_markdown(report)


async def test_position_closed_same_day_is_realised(db: AsyncSession) -> None:
    now = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    opened = datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    closed = datetime(2026, 8, 5, 5, 0, tzinfo=UTC)  # 10:30 IST, same day
    user = await create_test_user(db, email="rep2@example.com")
    stock = await make_stock(db, symbol="WONDERLA")
    sig = await _signal(
        db,
        stock.id,
        created=opened,
        entry="485.20",
        sl="456.20",
        tp="514.31",
        classification="swing",
    )
    pos = Position(
        user_id=user.id,
        stock_id=stock.id,
        mode="paper",
        side="LONG",
        quantity=68,
        avg_entry_price=Decimal("485.80"),
        current_sl=Decimal("456.20"),
        current_tp=Decimal("514.31"),
        trail_state="none",
        realized_pnl=Decimal("1856"),
        exit_price=Decimal("514.31"),
        exit_reason="tp_hit",
        opened_at=opened,
        closed_at=closed,
        signal_id=sig.id,
    )
    db.add(pos)
    _candles(
        db, stock.id, opened, [(1, "486", "515", "485", "514"), (30, "513", "515", "510", "514")]
    )
    await db.commit()

    report = await build_daily_report(db, day=date(2026, 8, 5), user_id=user.id, now=now)
    assert len(report.closed) == 1
    assert report.closed[0].closed_in_window is True
    assert report.realized_today == Decimal("1856")


async def test_next_day_close_shows_open_in_prior_day_report(db: AsyncSession) -> None:
    """Regression: a position opened day D and closed D+1 must appear as OPEN AT
    DAY END in D's report — never with D+1's exit price (temporal look-ahead)."""
    now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)  # report generated later
    opened = datetime(2026, 8, 4, 4, 0, tzinfo=UTC)  # 09:30 IST Tue
    closed = datetime(2026, 8, 5, 3, 56, tzinfo=UTC)  # 09:26 IST Wed (next day)
    user = await create_test_user(db, email="rep3@example.com")
    stock = await make_stock(db, symbol="DHAMPURSUG")
    sig = await _signal(
        db,
        stock.id,
        created=opened,
        direction="SELL",
        entry="141.33",
        sl="148.95",
        tp="132.85",
        classification="swing",
    )
    pos = Position(
        user_id=user.id,
        stock_id=stock.id,
        mode="paper",
        side="SHORT",
        quantity=262,
        avg_entry_price=Decimal("140.60"),
        current_sl=Decimal("148.95"),
        current_tp=Decimal("132.85"),
        trail_state="none",
        realized_pnl=Decimal("-2521"),
        exit_price=Decimal("149.90"),
        exit_reason="sl_hit",
        opened_at=opened,
        closed_at=closed,
        signal_id=sig.id,
    )
    db.add(pos)
    _candles(
        db,
        stock.id,
        opened,
        [(1, "141", "141", "139.9", "140"), (60, "140.5", "141", "140", "140.3")],
    )
    await db.commit()

    report = await build_daily_report(db, day=date(2026, 8, 4), user_id=user.id, now=now)
    assert len(report.opened) == 1
    row = report.opened[0]
    assert row.closed_in_window is False  # NOT shown as closed on Tue
    assert row in report.still_open
    assert not report.closed  # nothing closed on Tue
    md = render_markdown(report)
    assert "149.90" not in md  # Wed's exit price must not leak
    assert "open at EoD" in md


async def test_locked_profit_reported_when_stop_ratcheted_above_entry(db: AsyncSession) -> None:
    """Once the ₹ ladder has moved the stop into profit, the report shows the
    sealed ₹ (guaranteed if the stop holds) per trade and in the scorecard."""
    now = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    opened = datetime(2026, 8, 5, 4, 0, tzinfo=UTC)
    user = await create_test_user(db, email="rep4@example.com")
    user.profit_lock_enabled = True
    stock = await make_stock(db, symbol="STEELXIND")
    sig = await _signal(
        db, stock.id, created=opened, entry="500.00", sl="480.00",
        tp="560.00", classification="swing",
    )
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=100,
        avg_entry_price=Decimal("500.00"), current_sl=Decimal("512.00"),  # ratcheted +₹1200
        current_tp=Decimal("560.00"), trail_state="none",
        realized_pnl=Decimal("0"), opened_at=opened, signal_id=sig.id,
    )
    db.add(pos)
    _candles(
        db, stock.id, opened,
        [(1, "500", "530", "500", "528"), (30, "520", "522", "515", "518")],
    )
    await db.commit()

    report = await build_daily_report(db, day=date(2026, 8, 5), user_id=user.id, now=now)
    row = report.opened[0]
    assert row.locked_inr == Decimal("1200.00")  # (512 − 500) × 100
    assert report.locked_total == Decimal("1200.00")
    assert "sealed ₹1,200" in render_markdown(report)
