"""Tests for the daily trading-analysis report generator.

Pure-function coverage (chase / oversize math and tape MFE/MAE with timing),
plus DB-integration tests through the seam that assembles a day's report —
including a regression test for the temporal look-ahead bug where a position
opened on day D but closed on D+1 was rendered as closed (with D+1's exit) in
D's report.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.fo_data import FoBhavcopy, IndiaVixDaily
from app.models.market_data import Ohlcv1m
from app.models.signal import Signal
from app.models.trading import Position
from app.services.daily_report import (
    _open_book_mtm,
    _render_fo_section,
    _render_shadow_section,
    build_daily_report,
    build_fo_health,
    build_shadow_health,
    build_week_summary,
    chase_metrics,
    render_markdown,
    render_week_markdown,
    tape_excursion,
)
from app.services.fo_suggestions import DEFAULT_SELL_RULES
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


# ── F&O engine health (the two open calibration decisions) ────────────────────
#
# These exist so the §9.3 (weeklies excluded) and §9.7 (stale vol gates warn,
# not reject) decisions can be reviewed on evidence rather than recollection.
# The engine returning `[]` was ALREADY the ambiguity that hid a month-long
# outage — so "dark" must always arrive with its reason attached.

_FO_DAY = date(2026, 8, 3)
_FO_MONTHLY = date(2026, 9, 28)      # 56 DTE — owns the only FUT row
_FO_WEEKLY = date(2026, 8, 25)       # 22 DTE — in a 20–45 window, NO future
_FO_SPOT = 50000.0
_FO_FUT = 50250.0
_FO_RATE = 0.065


async def _seed_fo(
    db: AsyncSession, tc: object, *, expiries: list[date], vix: str = "14"
) -> None:
    """A BANKNIFTY board with futures ONLY at `_FO_MONTHLY` — the real NSE shape
    (weekly options, monthly futures). `expiries` chooses which option chains
    exist, so a test can present only-a-weekly or weekly-then-monthly."""
    hist_strike = 50300                       # on the chain's 100-point grid
    for i, iv in enumerate([0.15, 0.17, 0.19, 0.21, 0.24, 0.27, 0.30]):
        d = _FO_DAY - timedelta(days=7 - i)
        t = (_FO_MONTHLY - d).days / 365.0
        px = tc.option_price("call", [(_FO_FUT, float(hist_strike), t, _FO_RATE, 0.0, iv)])[0]  # type: ignore[attr-defined]
        db.add(FoBhavcopy(trade_date=d, symbol="BANKNIFTY", instrument="FUT",
                          expiry_date=_FO_MONTHLY, strike=Decimal("0"),
                          close=Decimal(str(_FO_FUT)),
                          underlying_close=Decimal(str(_FO_SPOT)), open_interest=1000))
        db.add(FoBhavcopy(trade_date=d, symbol="BANKNIFTY", instrument="CE",
                          expiry_date=_FO_MONTHLY, strike=Decimal(str(hist_strike)),
                          close=Decimal(str(round(px, 2))), open_interest=1000))
    db.add(FoBhavcopy(trade_date=_FO_DAY, symbol="BANKNIFTY", instrument="FUT",
                      expiry_date=_FO_MONTHLY, strike=Decimal("0"),
                      close=Decimal(str(_FO_FUT)),
                      underlying_close=Decimal(str(_FO_SPOT)), open_interest=1000))
    strikes = [float(k) for k in range(44000, 56001, 100)]
    for e in expiries:
        t = (e - _FO_DAY).days / 365.0
        calls = tc.option_price("call", [(_FO_FUT, k, t, _FO_RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
        puts = tc.option_price("put", [(_FO_FUT, k, t, _FO_RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
        for k, cp, pp in zip(strikes, calls, puts, strict=True):
            db.add(FoBhavcopy(trade_date=_FO_DAY, symbol="BANKNIFTY", instrument="CE",
                              expiry_date=e, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(cp, 2))), open_interest=1000))
            db.add(FoBhavcopy(trade_date=_FO_DAY, symbol="BANKNIFTY", instrument="PE",
                              expiry_date=e, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(pp, 2))), open_interest=1000))
    # FIVE sessions, not four: `vix_regime` bands "high" on percentile > 75, and
    # the max of four values sits at exactly 75 — which reads "normal".
    for i, v in enumerate(["20", "19", "18", "17", vix]):
        db.add(IndiaVixDaily(trade_date=_FO_DAY - timedelta(days=4 - i), close=Decimal(v)))
    await db.commit()


_ONLY_BANKNIFTY = replace(DEFAULT_SELL_RULES, allowed_underlyings=frozenset({"BANKNIFTY"}))


async def test_fo_health_names_the_monthly_only_policy_when_it_goes_dark(
    db: AsyncSession,
) -> None:
    """THE REVIEW HOOK for phase-04 §9.3. Only a weekly is in window, so the
    monthly-only policy stands the engine down. The report must say THAT — not
    merely that there were no candidates, which is what hid the original bug."""
    tc = pytest.importorskip("tradecore")
    await _seed_fo(db, tc, expiries=[_FO_WEEKLY])
    rules = replace(_ONLY_BANKNIFTY, dte_min=20, dte_max=30)   # weekly 22 in, monthly 56 out

    rows = await build_fo_health(db, day=_FO_DAY, rules=rules)
    assert len(rows) == 1
    h = rows[0]
    assert h.verdict == "dark" and h.candidates == 0
    assert h.in_window == [_FO_WEEKLY]
    assert "require_exact_expiry_future" in h.reason
    assert "no ELIGIBLE expiry" in h.reason

    md = _render_fo_section(rows)
    body = "\n".join(md)
    assert "Monthly-only policy cost you today" in body
    assert "BANKNIFTY" in body and _FO_WEEKLY.isoformat() in body


async def test_fo_health_reports_the_monthly_when_the_walk_reaches_it(
    db: AsyncSession,
) -> None:
    """The other side of the same decision: a weekly in FRONT of an in-window
    monthly must not stand the engine down — the walk reaches the monthly and
    the report shows which expiry was actually priced, off an exact future."""
    tc = pytest.importorskip("tradecore")
    await _seed_fo(db, tc, expiries=[_FO_WEEKLY, _FO_MONTHLY])
    rules = replace(_ONLY_BANKNIFTY, dte_min=20, dte_max=60)   # BOTH in window

    h = (await build_fo_health(db, day=_FO_DAY, rules=rules))[0]
    assert h.expiry == _FO_MONTHLY, "must walk past the weekly to the monthly"
    assert h.forward_source == "fut_exact"
    assert h.in_window == [_FO_WEEKLY, _FO_MONTHLY]
    assert "require_exact_expiry_future" not in h.reason
    assert "Monthly-only policy cost you today" not in "\n".join(_render_fo_section([h]))


async def test_fo_health_distinguishes_a_veto_from_a_no_trade(db: AsyncSession) -> None:
    """A dark day has several causes and they demand different responses. A
    risk-off VIX veto must never be reported as 'nothing qualified'."""
    tc = pytest.importorskip("tradecore")
    await _seed_fo(db, tc, expiries=[_FO_MONTHLY], vix="45")   # last = max → band "high"
    rules = replace(_ONLY_BANKNIFTY, dte_min=20, dte_max=60)

    h = (await build_fo_health(db, day=_FO_DAY, rules=rules))[0]
    assert h.verdict == "dark"
    assert h.vix_band == "high"
    assert "risk-off veto" in h.reason


async def test_fo_health_flags_a_stale_vol_gate(db: AsyncSession) -> None:
    """THE REVIEW HOOK for phase-04 §9.7. The vol gate is bounded against
    look-ahead but not ALIGNED to the priced day, so it can authorise a trade on
    weeks-old evidence. That was left as a warning rather than a rejection — so
    the warning has to be visible somewhere the user actually reads."""
    tc = pytest.importorskip("tradecore")
    await _seed_fo(db, tc, expiries=[_FO_MONTHLY])
    rules = replace(_ONLY_BANKNIFTY, dte_min=20, dte_max=60)

    # Ask for a day well after the last recorded bhavcopy: the chain and the
    # gate both fall back to _FO_DAY, but the *report* day has moved on.
    later = _FO_DAY + timedelta(days=30)
    h = (await build_fo_health(db, day=later, rules=rules))[0]
    assert h.data_day == _FO_DAY
    assert h.data_lag_days == 30
    body = "\n".join(_render_fo_section([h]))
    assert "F&O data is 30 day(s) behind" in body


async def test_fo_health_reports_no_data_rather_than_a_silent_row(
    db: AsyncSession,
) -> None:
    """An empty F&O board is a data problem, not a trading answer."""
    rows = await build_fo_health(db, day=_FO_DAY, rules=_ONLY_BANKNIFTY)
    assert [h.verdict for h in rows] == ["no data"]
    assert "no F&O bhavcopy" in rows[0].reason


async def test_daily_report_carries_the_fo_section(db: AsyncSession) -> None:
    """Seam: the F&O attribution reaches the rendered Markdown even on a day
    with no equity trades — the engine's silence is itself the finding."""
    tc = pytest.importorskip("tradecore")
    await _seed_fo(db, tc, expiries=[_FO_WEEKLY])
    user = await create_test_user(db, email="fohealth@example.com")

    r = await build_daily_report(
        db, day=_FO_DAY, user_id=user.id, now=datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    )
    assert r.opened == [] and r.closed == []
    assert [h.symbol for h in r.fo_health] == sorted(DEFAULT_SELL_RULES.allowed_underlyings)
    md = render_markdown(r)
    assert "## 7. F&O option-selling engine" in md
    assert "Suggestions only" in md
    # BANKNIFTY has a board; the other two indices have none. Both are reported.
    assert "no F&O bhavcopy" in md


# ── §8 intraday shadow layer ────────────────────────────────────────────────
# Shadow profiles exist to replace a negative BACKTEST verdict with FORWARD
# evidence, so a silent layer is a failed layer: "no evidence yet" and "evidence
# says no" must never look the same in the report.


async def _shadow_profile(db: AsyncSession, key: str = "pdh_shadow") -> None:
    from app.models.profile import StrategyProfile

    db.add(
        StrategyProfile(
            key=key,
            version=1,
            name=key,
            description="t",
            style="intraday",
            timeframe="15m",
            schedule="intraday_15m",
            universe_spec={"kind": "symbols", "value": ["X"]},
            setup_conditions=[],
            weight_multipliers={},
            min_confidence=70,
            risk_template={"kind": "rr", "ratio": "1.5"},
            validity_spec=None,
            status="shadow",
            config_hash=f"h-{key}",
        )
    )
    await db.flush()


async def test_shadow_health_empty_when_no_profile_is_in_shadow(
    db: AsyncSession,
) -> None:
    rows = await build_shadow_health(db, day=date(2026, 8, 10))
    assert rows == []
    assert "_No profiles are running in shadow._" in "\n".join(
        _render_shadow_section(rows)
    )


async def test_shadow_health_says_not_a_trading_day(db: AsyncSession) -> None:
    """A Saturday zero must not read as a strategy failure."""
    await _shadow_profile(db)
    await db.commit()

    rows = await build_shadow_health(db, day=date(2026, 8, 8))  # Saturday
    assert len(rows) == 1
    assert rows[0].minted == 0
    assert "not a trading day" in (rows[0].reason or "")


async def test_shadow_health_blames_missing_bars_not_the_strategy(
    db: AsyncSession,
) -> None:
    """The failure that would otherwise be invisible.

    No 15m bars on a trading day means the live worker produced nothing —
    usually the Kite token ritual. Reporting that as "the setups did not
    trigger" would send the reader off to tune a strategy that never ran.
    """
    await _shadow_profile(db)
    await db.commit()

    rows = await build_shadow_health(db, day=date(2026, 8, 10))  # Monday
    assert rows[0].minted == 0
    reason = rows[0].reason or ""
    assert "NO 15m bars" in reason
    assert "Kite token" in reason


async def test_shadow_section_flags_a_wholly_silent_day(db: AsyncSession) -> None:
    await _shadow_profile(db)
    await db.commit()

    rows = await build_shadow_health(db, day=date(2026, 8, 10))
    md = "\n".join(_render_shadow_section(rows))
    assert "## 8. Intraday shadow layer" in md
    assert "never tradeable" in md
    assert "Nothing minted today" in md


# ── 6.8.4 — carried-position rolling MFE/MAE + weekly open-MTM series ──────────
async def test_carried_position_rolling_mfe_no_lookahead(db: AsyncSession) -> None:
    """6.8.4: a position opened on a PRIOR day is 'carried' — it gets the rolling
    MFE/MAE narrative, marked to each day's cutoff with NO future-bar leakage."""
    user = await create_test_user(db, email="carry@example.com")
    stock = await make_stock(db, symbol="INFY")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)  # Mon 09:30 IST
    sig = await _signal(db, stock.id, created=opened, entry="100", sl="95", tp="120")
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("95"), current_tp=Decimal("120"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=opened, signal_id=sig.id,
    )
    db.add(pos)
    # Mon high 103 · Tue high 106 · Wed high 112 — the peak grows across days.
    for day_n, row in [
        (3, (1, "100", "103", "99", "102")),
        (4, (1, "102", "106", "101", "105")),
        (5, (1, "105", "112", "104", "110")),
    ]:
        _candles(db, stock.id, datetime(2026, 8, day_n, 4, 0, tzinfo=UTC), [row])
    await db.commit()

    # Tue report (D-1): carried, MFE bounded to Tue cutoff → sees 106, NOT 112.
    tue = await build_daily_report(
        db, day=date(2026, 8, 4), user_id=user.id, now=datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
    )
    assert not tue.opened  # opened Monday, not today
    assert len(tue.carried) == 1
    carried = tue.carried[0]
    assert carried.symbol == "INFY"
    assert carried.excursion is not None
    assert carried.excursion.mfe_price == Decimal("106")  # no look-ahead into Wed's 112
    assert carried.excursion.mfe_r == Decimal("1.200")
    md = render_markdown(tue)
    assert "Carried positions" in md and "INFY" in md
    # show_date=True must render the OPEN DATE (08-03), not just a time — the whole
    # point of the multi-day narrative (a regression to time-only `_ist` would pass
    # "INFY" but drop the date).
    assert "08-03" in md

    # Wed report (D): the rolling MFE advances to 112.
    wed = await build_daily_report(
        db, day=date(2026, 8, 5), user_id=user.id, now=datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    )
    assert len(wed.carried) == 1
    assert wed.carried[0].excursion is not None
    assert wed.carried[0].excursion.mfe_price == Decimal("112")
    assert wed.carried[0].excursion.mfe_r == Decimal("2.400")


async def test_weekly_open_mtm_series_per_trading_day(db: AsyncSession) -> None:
    """6.8.4: the weekly open-book MTM is a per-trading-day series, not latest-only."""
    user = await create_test_user(db, email="wk@example.com")
    stock = await make_stock(db, symbol="TCS")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)  # Mon 09:30 IST
    sig = await _signal(db, stock.id, created=opened, entry="100", sl="95", tp="130")
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("95"), current_tp=Decimal("130"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=opened, signal_id=sig.id,
    )
    db.add(pos)
    # one close per day: Mon 102 · Tue 104 · Wed 103 · Thu 106 · Fri 110
    for d, cl in [(3, "102"), (4, "104"), (5, "103"), (6, "106"), (7, "110")]:
        base = datetime(2026, 8, d, 4, 0, tzinfo=UTC)
        _candles(db, stock.id, base, [(1, cl, cl, cl, cl)])
    await db.commit()

    wk = await build_week_summary(
        db, monday=date(2026, 8, 3), user_id=user.id, now=datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
    )
    # one entry per trading day (Mon–Fri; no holidays seeded → all trading days)
    assert [d for d, _ in wk.open_mtm_series] == [date(2026, 8, i) for i in range(3, 8)]
    marks = dict(wk.open_mtm_series)
    assert marks[date(2026, 8, 3)] == Decimal("20.00")  # 10 × (102 − 100)
    assert marks[date(2026, 8, 5)] == Decimal("30.00")  # 10 × (103 − 100)
    assert marks[date(2026, 8, 7)] == Decimal("100.00")  # 10 × (110 − 100)
    assert wk.open_mtm_latest == Decimal("100.00")  # latest = last trading day
    assert "per trading day" in render_week_markdown(wk)


async def test_open_book_mtm_no_future_bar_leakage(db: AsyncSession) -> None:
    """6.8.4: _open_book_mtm marks to the last close ≤ cutoff — a later bar (even
    same day) never leaks into the mark."""
    user = await create_test_user(db, email="leak@example.com")
    stock = await make_stock(db, symbol="WIPRO")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("95"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=opened,
    )
    db.add(pos)
    # a bar at +5 min (close 101) and a later spike at +120 min (close 130)
    _candles(
        db, stock.id, opened,
        [(5, "100", "101", "100", "101"), (120, "101", "131", "101", "130")],
    )
    await db.commit()
    cutoff = datetime(2026, 8, 3, 4, 30, tzinfo=UTC)  # before the +120 spike
    mtm = await _open_book_mtm(db, user.id, cutoff)
    assert mtm == Decimal("10.00")  # marks to 101, never the future 130


async def test_open_book_mtm_excludes_closed_and_skips_no_tape(db: AsyncSession) -> None:
    """6.8.4 (test-guardian #1): _open_book_mtm marks only positions OPEN at the
    cutoff, and skips a stock with no tape — the None-mark and closed-boundary
    branches. (a) open+bar counts, (b) closed BEFORE cutoff excluded, (c) open but
    no tape skipped, (d) closed AFTER cutoff still counted as open-as-of-cutoff."""
    user = await create_test_user(db, email="mtm@example.com")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)
    cutoff = datetime(2026, 8, 3, 4, 30, tzinfo=UTC)

    a = await make_stock(db, symbol="STKA")
    _candles(db, a.id, opened, [(5, "100", "101", "100", "101")])  # → +10
    b = await make_stock(db, symbol="STKB")
    _candles(db, b.id, opened, [(5, "100", "120", "100", "120")])  # closed early → excluded
    c = await make_stock(db, symbol="STKC")  # no tape at all
    d = await make_stock(db, symbol="STKD")
    _candles(db, d.id, opened, [(5, "100", "105", "100", "105")])  # closed later → +50

    def _pos(stock_id: int, closed_at: datetime | None = None) -> Position:
        return Position(
            user_id=user.id, stock_id=stock_id, mode="paper", side="LONG", quantity=10,
            avg_entry_price=Decimal("100"), current_sl=Decimal("95"), trail_state="none",
            realized_pnl=Decimal("0"), opened_at=opened, closed_at=closed_at,
        )

    db.add(_pos(a.id))
    db.add(_pos(b.id, closed_at=datetime(2026, 8, 3, 4, 15, tzinfo=UTC)))  # before cutoff
    db.add(_pos(c.id))
    db.add(_pos(d.id, closed_at=datetime(2026, 8, 3, 5, 0, tzinfo=UTC)))  # after cutoff
    await db.commit()

    # only (a) +10 and (d) +50; (b) excluded (closed early), (c) skipped (no tape)
    assert await _open_book_mtm(db, user.id, cutoff) == Decimal("60.00")


async def test_no_carried_section_when_none_carried(db: AsyncSession) -> None:
    """6.8.4 (test-guardian #3): the 'Carried positions' header appears only when
    there ARE carried holds — an opened-today-only report must not emit it empty."""
    user = await create_test_user(db, email="nocarry@example.com")
    stock = await make_stock(db, symbol="HDFCBANK")
    opened = datetime(2026, 8, 5, 4, 0, tzinfo=UTC)  # opened TODAY
    sig = await _signal(db, stock.id, created=opened, entry="100", sl="95", tp="120")
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("95"), current_tp=Decimal("120"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=opened, signal_id=sig.id,
    )
    db.add(pos)
    _candles(db, stock.id, opened, [(1, "100", "103", "99", "102")])
    await db.commit()
    report = await build_daily_report(
        db, day=date(2026, 8, 5), user_id=user.id, now=datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    )
    assert report.opened and not report.carried
    assert "Carried positions" not in render_markdown(report)


async def test_carried_short_position_mark_sign(db: AsyncSession) -> None:
    """6.8.4 (test-guardian #4): a SHORT carried position — a price RISE is adverse
    (negative mark) and its MFE is the lowest low."""
    user = await create_test_user(db, email="short@example.com")
    stock = await make_stock(db, symbol="ADANIENT")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)  # prior day
    sig = await _signal(
        db, stock.id, created=opened, entry="100", sl="105", tp="90", direction="SELL"
    )
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="SHORT", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("105"), current_tp=Decimal("90"),
        trail_state="none", realized_pnl=Decimal("0"), opened_at=opened, signal_id=sig.id,
    )
    db.add(pos)
    # dips to 96 (favourable for a short), then rises to close 104 (adverse)
    _candles(db, stock.id, opened, [(1, "100", "101", "96", "98")])
    _candles(db, stock.id, datetime(2026, 8, 4, 4, 0, tzinfo=UTC), [(1, "99", "106", "99", "104")])
    await db.commit()
    report = await build_daily_report(
        db, day=date(2026, 8, 4), user_id=user.id, now=datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
    )
    assert len(report.carried) == 1
    assert report.carried[0].excursion is not None
    assert report.carried[0].excursion.mfe_price == Decimal("96")  # lowest low best for a short
    # marked to last close 104 → adverse for a short → 10 × (100 − 104) = −40
    mtm = await _open_book_mtm(db, user.id, datetime(2026, 8, 4, 10, 0, tzinfo=UTC))
    assert mtm == Decimal("-40.00")


async def test_weekly_series_skips_future_and_holiday(db: AsyncSession) -> None:
    """6.8.4 (test-guardian #5): the per-day series covers only ELAPSED trading days
    — a mid-week run stops at 'now', and a seeded holiday is skipped."""
    from app.models.market_calendar import NseHoliday

    user = await create_test_user(db, email="wkskip@example.com")
    stock = await make_stock(db, symbol="SBIN")
    opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)  # Mon
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
        avg_entry_price=Decimal("100"), current_sl=Decimal("95"), trail_state="none",
        realized_pnl=Decimal("0"), opened_at=opened,
    )
    db.add(pos)
    for d, cl in [(3, "102"), (4, "104"), (5, "103")]:  # Mon/Tue/Wed bars
        _candles(db, stock.id, datetime(2026, 8, d, 4, 0, tzinfo=UTC), [(1, cl, cl, cl, cl)])
    db.add(NseHoliday(holiday_date=date(2026, 8, 4), name="Test Holiday"))  # Tue is a holiday
    await db.commit()

    # run mid-week Wed 13:30 IST → series = Mon + Wed only (Tue holiday, Thu/Fri future)
    wk = await build_week_summary(
        db, monday=date(2026, 8, 3), user_id=user.id, now=datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    )
    assert [d for d, _ in wk.open_mtm_series] == [date(2026, 8, 3), date(2026, 8, 5)]
