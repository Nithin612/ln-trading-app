"""Regime taxonomy + eligibility overlay + shadow measurement (Phase 6).

Pure (no DB): the canonical regime bucketing, the gate's fail-open policy, its
mode-aware order verdict, and the live shadow measurement over synthetic rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.models.signal import Signal
from app.services.entry_attribution import Row, _regime_bucket
from app.services.regime_gate_shadow import measure
from app.signals import regime as rg
from app.signals import regime_guard

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _sig(explanation: str | None) -> Signal:
    """A Signal carrying only an ADX factor with the given explanation (None = no
    ADX factor at all)."""
    adx = {"weight": 5, "score": 0.0, "explanation": explanation}
    return Signal(factor_scores={} if explanation is None else {"ADX": adx})


# --------------------------------------------------------------------------- #
# regime taxonomy                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "level,bucket",
    [
        (None, rg.NA),
        (0.0, rg.CHOPPY),
        (19.9, rg.CHOPPY),
        (20.0, rg.TRANSITIONAL),
        (24.9, rg.TRANSITIONAL),
        (25.0, rg.TRENDING),
        (40.0, rg.TRENDING),
    ],
)
def test_adx_regime_thresholds(level: float | None, bucket: str) -> None:
    assert rg.adx_regime(level) == bucket


def test_parse_adx_level() -> None:
    assert rg.parse_adx_level("ADX=27.2 trending; +DI=30 > -DI=10 bullish") == 27.2
    assert rg.parse_adx_level("ADX=18 weak trend (< 20)") == 18.0
    assert rg.parse_adx_level("no adx here") is None
    assert rg.parse_adx_level(None) is None
    assert rg.parse_adx_level(42) is None


def test_regime_from_factor_scores_fails_to_na() -> None:
    got = rg.regime_from_factor_scores({"ADX": {"explanation": "ADX=22.0 moderate"}})
    assert got == rg.TRANSITIONAL
    assert rg.regime_from_factor_scores({"DOW_TREND": {"explanation": "up"}}) == rg.NA  # no ADX
    assert rg.regime_from_factor_scores({}) == rg.NA
    assert rg.regime_from_factor_scores(None) == rg.NA


def test_labels_match_attribution_canon() -> None:
    # entry_attribution now delegates to rg — the two must never diverge.
    assert _regime_bucket(22.5) == rg.TRANSITIONAL == "transitional (20–25)"
    assert _regime_bucket(10.0) == rg.CHOPPY
    assert _regime_bucket(30.0) == rg.TRENDING


# --------------------------------------------------------------------------- #
# the gate policy                                                             #
# --------------------------------------------------------------------------- #


def test_skip_set_is_transitional_only() -> None:
    assert regime_guard.SKIP_REGIMES == frozenset({rg.TRANSITIONAL})


def test_is_eligible_and_fail_open() -> None:
    assert regime_guard.is_eligible(_sig("ADX=30 trending")) is True
    assert regime_guard.is_eligible(_sig("ADX=22 moderate (20-25)")) is False  # transitional gated
    assert regime_guard.is_eligible(_sig("ADX=10 weak")) is True               # choppy NOT gated
    assert regime_guard.is_eligible(_sig(None)) is True                        # fail-open: no ADX


def test_order_block_reason_only_active_blocks() -> None:
    transitional = _sig("ADX=22 moderate (20-25)")
    trending = _sig("ADX=30 trending")
    # off / shadow never block — the wiring is inert until the flip
    for mode in ("off", "shadow"):
        assert regime_guard.order_block_reason(transitional, mode) is None
        assert regime_guard.order_block_reason(trending, mode) is None
    # active blocks only the ineligible regime
    reason = regime_guard.order_block_reason(transitional, "active")
    assert reason is not None and "regime" in reason.lower()
    assert regime_guard.order_block_reason(trending, "active") is None
    assert regime_guard.order_block_reason(_sig(None), "active") is None  # fail-open


# --------------------------------------------------------------------------- #
# shadow measurement                                                          #
# --------------------------------------------------------------------------- #


def _row(status: str, adx: float, *, rr: float | None = None, day: int = 0) -> Row:
    return Row(
        status=status,
        mfe_r=None,
        mae_r=None,
        rr=rr,
        confidence=75,
        adx=adx,
        direction="BUY",
        setup="t",
        created_at=BASE + timedelta(days=day),
        timeframe="1d",
        factors={},
    )


def test_measure_splits_kept_and_killed() -> None:
    rows = [
        _row("tp_first", 30.0, rr=2.0, day=0),   # trending win  → kept
        _row("sl_first", 30.0, day=1),           # trending loss → kept
        _row("sl_first", 22.0, day=2),           # transitional loss → killed
        _row("sl_first", 22.0, day=3),           # transitional loss → killed
    ]
    res = measure(rows)
    assert res.baseline.trades == 4
    assert res.gated.trades == 2      # the two trending
    assert res.killed.trades == 2     # the two transitional
    # kept realized R = [+2, -1] → +1 total; killed = [-1, -1] → -2
    assert res.gated.total_r == pytest.approx(1.0)
    assert res.killed.total_r == pytest.approx(-2.0)
    # the suppressed set is net-negative → the flip would be justified
    assert res.killed.mean_exp_r == pytest.approx(-1.0)
    assert res.gated.mean_exp_r > res.baseline.mean_exp_r


def test_measure_empty() -> None:
    res = measure([])
    assert res.baseline.trades == 0
    assert res.killed.trades == 0
