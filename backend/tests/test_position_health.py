"""Unit tests for the emergency-exit watcher (app/trading/position_health.py).

Pure function — no DB, no clock. Numbers are hand-chosen so the R-multiples
and reward:risk ratios are exact and obvious.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.trading.position_health import (
    DEEP_MAE,
    RR_INVERTED,
    STALE,
    THESIS_BREAK,
    TREND_DEAD,
    HealthVerdict,
    assess_position_health,
)

NOW = datetime(2026, 7, 31, 6, 0, tzinfo=UTC)
FUTURE = NOW + timedelta(days=3)
PAST = NOW - timedelta(hours=1)

# LONG reference trade: entry 100, SL 96 (R = 4), TP 112.
LONG = dict(side="LONG", entry=Decimal("100"), stop_loss=Decimal("96"), take_profit=Decimal("112"))


def _codes(health):
    return {r.code for r in health.reasons}


def test_healthy_trade_is_hold():
    """Green, trending, target ahead → nothing to flag."""
    h = assess_position_health(
        **LONG, current_price=Decimal("104"), regime_er=0.6, validity_until=FUTURE, now=NOW
    )
    assert h.verdict is HealthVerdict.HOLD
    assert h.reasons == []
    # +4 above entry on a 4-wide R → 1R in profit.
    assert h.drawdown_r == -1.0


def test_thesis_break_is_cut_and_suppresses_deep_mae():
    """Price through the stop → hard CUT; we don't also emit deep-MAE noise."""
    h = assess_position_health(
        **LONG, current_price=Decimal("95"), regime_er=0.6, validity_until=FUTURE, now=NOW
    )
    assert h.verdict is HealthVerdict.CUT
    assert THESIS_BREAK in _codes(h)
    assert DEEP_MAE not in _codes(h)


def test_deep_mae_before_the_stop():
    """0.9R underwater but still above the stop → CUT via deep-MAE."""
    h = assess_position_health(
        **LONG, current_price=Decimal("96.4"), regime_er=0.6, validity_until=FUTURE, now=NOW
    )
    assert h.verdict is HealthVerdict.CUT
    assert DEEP_MAE in _codes(h)
    assert THESIS_BREAK not in _codes(h)
    assert round(h.drawdown_r, 2) == 0.9


def test_trend_death_escalates_only_when_underwater():
    """Choppy regime is a WATCH while green, a CUT once red."""
    green = assess_position_health(
        **LONG, current_price=Decimal("101"), regime_er=0.1, validity_until=FUTURE, now=NOW
    )
    assert green.verdict is HealthVerdict.WATCH
    assert TREND_DEAD in _codes(green)

    red = assess_position_health(
        **LONG, current_price=Decimal("99"), regime_er=0.1, validity_until=FUTURE, now=NOW
    )
    assert red.verdict is HealthVerdict.CUT
    assert TREND_DEAD in _codes(red)


def test_rr_inversion_only_flags_a_losing_trade():
    """Underwater with more left to lose than to gain → CUT."""
    # px 98: reward_rem = 112-98 = 14, risk_rem = 98-96 = 2 → rr 7.0, healthy.
    ok = assess_position_health(
        **LONG, current_price=Decimal("98"), regime_er=0.6, validity_until=FUTURE, now=NOW
    )
    assert RR_INVERTED not in _codes(ok)

    # px 96.5: reward_rem = 15.5, risk_rem = 0.5 → rr 31; still healthy reward.
    # Build inversion instead with a nearer target.
    inverted = assess_position_health(
        side="LONG",
        entry=Decimal("100"),
        stop_loss=Decimal("96"),
        take_profit=Decimal("100.4"),
        current_price=Decimal("99"),  # reward_rem 1.4, risk_rem 3.0 → rr 0.47, adverse
        regime_er=0.6,
        validity_until=FUTURE,
        now=NOW,
    )
    assert inverted.verdict is HealthVerdict.CUT
    assert RR_INVERTED in _codes(inverted)
    assert round(inverted.rr_remaining, 2) == 0.47


def test_rr_inversion_not_flagged_on_a_winner():
    """A green trade near its target (small remaining reward vs full risk) is a
    hold, not a cut — you trail the stop, you don't panic-exit."""
    h = assess_position_health(
        **LONG, current_price=Decimal("110"), regime_er=0.6, validity_until=FUTURE, now=NOW
    )
    # reward_rem 2, risk_rem 14 → rr 0.14 but the trade is in profit.
    assert h.rr_remaining is not None and h.rr_remaining < 1.0
    assert RR_INVERTED not in _codes(h)
    assert h.verdict is HealthVerdict.HOLD


def test_stale_past_validity():
    """Held past the signal window: WATCH if green, CUT if red."""
    green = assess_position_health(
        **LONG, current_price=Decimal("103"), regime_er=0.6, validity_until=PAST, now=NOW
    )
    assert green.verdict is HealthVerdict.WATCH
    assert STALE in _codes(green)

    red = assess_position_health(
        **LONG, current_price=Decimal("99"), regime_er=0.6, validity_until=PAST, now=NOW
    )
    assert red.verdict is HealthVerdict.CUT
    assert STALE in _codes(red)


def test_short_thesis_break_mirrors():
    """SHORT: price at/above the stop is the break."""
    h = assess_position_health(
        side="SHORT",
        entry=Decimal("100"),
        stop_loss=Decimal("104"),
        take_profit=Decimal("88"),
        current_price=Decimal("104.5"),
        regime_er=0.6,
        validity_until=FUTURE,
        now=NOW,
    )
    assert h.verdict is HealthVerdict.CUT
    assert THESIS_BREAK in _codes(h)


def test_missing_price_limits_to_regime_and_expiry():
    """No live price: can't judge break/MAE/RR — regime + staleness still flag,
    as WATCH (adverse is unknown, so nothing escalates to CUT)."""
    h = assess_position_health(
        **LONG, current_price=None, regime_er=0.1, validity_until=PAST, now=NOW
    )
    assert h.verdict is HealthVerdict.WATCH
    assert _codes(h) == {TREND_DEAD, STALE}
    assert h.drawdown_r is None


def test_naive_validity_does_not_raise():
    """A naive validity_until (mis-fed by some future caller) is coerced to UTC
    rather than crashing the whole positions list."""
    naive_past = datetime(2026, 7, 31, 5, 0)  # no tzinfo, before NOW
    h = assess_position_health(
        **LONG, current_price=Decimal("99"), regime_er=0.6, validity_until=naive_past, now=NOW
    )
    assert h.verdict is HealthVerdict.CUT
    assert STALE in _codes(h)


def test_missing_stop_loss_skips_price_based_checks():
    h = assess_position_health(
        side="LONG",
        entry=Decimal("100"),
        stop_loss=None,
        take_profit=Decimal("112"),
        current_price=Decimal("90"),  # deep loss, but no SL to measure against
        regime_er=0.6,
        validity_until=FUTURE,
        now=NOW,
    )
    assert h.verdict is HealthVerdict.HOLD
    assert h.drawdown_r is None
    assert h.reasons == []
