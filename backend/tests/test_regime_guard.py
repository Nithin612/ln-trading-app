"""Regime taxonomy + eligibility overlay + shadow measurement (Phase 6).

Pure (no DB): the canonical regime bucketing, the gate's fail-open policy, its
mode-aware order verdict, and the live shadow measurement over synthetic rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.models.signal import Signal
from app.services.entry_attribution import Row, _regime_bucket
from app.services.regime_gate_shadow import (
    FORWARD_EVIDENCE_REVIEW_DATE,
    forward_evidence_ready,
    measure,
    readiness_line,
)
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
# branch recovery (first-class ADX level, Phase 6) — committed signals recover  #
# regime from the frozen factor's DECISION BRANCH, not the 0.1-rounded number,  #
# so a band-edge signal is bucketed by the comparison the engine actually made. #
# --------------------------------------------------------------------------- #


def test_regime_from_branch_reads_the_frozen_factor_phrasing() -> None:
    assert rg.regime_from_branch("ADX=27.2 trending; +DI=30 > -DI=10 bullish") == rg.TRENDING
    assert (
        rg.regime_from_branch("ADX=18.0 weak trend (< 20) — requires +5% confidence")
        == rg.CHOPPY
    )
    assert (
        rg.regime_from_branch("ADX=22.0 moderate (20-25), no strong directional signal")
        == rg.TRANSITIONAL
    )
    # no branch phrase → None, so the caller falls back to the numeric parse
    assert rg.regime_from_branch("ADX=22.0") is None
    assert rg.regime_from_branch(None) is None


def test_regime_from_factor_scores_fixes_the_20_edge_misbucket() -> None:
    """CANARY: raw ADX 19.97 rounds to 'ADX=20.0' but the frozen factor took the
    '<20 weak trend' branch. Branch recovery reads CHOPPY (eligible); the OLD
    numeric re-bucket of the rounded 20.0 read TRANSITIONAL — wrongly suppressed
    in ACTIVE mode. Fails on the pre-branch code."""
    expl = "ADX=20.0 weak trend (< 20) — requires +5% confidence"
    fs = {"ADX": {"weight": 5, "score": 0.0, "explanation": expl}}
    assert rg.regime_from_factor_scores(fs) == rg.CHOPPY
    # the numeric path this replaced would have said transitional:
    assert rg.adx_regime(rg.parse_adx_level(expl)) == rg.TRANSITIONAL


def test_regime_from_factor_scores_fixes_the_25_edge_misbucket() -> None:
    """CANARY (upper mirror): raw ADX 24.97 rounds to 'ADX=25.0' in the '20-25
    moderate' branch → branch reads TRANSITIONAL (correctly gated); the OLD numeric
    re-bucket of 25.0 read TRENDING and let the bad entry through."""
    expl = "ADX=25.0 moderate (20-25), no strong directional signal"
    fs = {"ADX": {"weight": 5, "score": 0.0, "explanation": expl}}
    assert rg.regime_from_factor_scores(fs) == rg.TRANSITIONAL
    assert rg.adx_regime(rg.parse_adx_level(expl)) == rg.TRENDING


def test_regime_from_factor_scores_falls_back_to_numeric_parse() -> None:
    # a non-standard explanation carrying a number but no branch phrase
    assert rg.regime_from_factor_scores({"ADX": {"explanation": "ADX=22.5"}}) == rg.TRANSITIONAL
    assert rg.regime_from_factor_scores({"ADX": {"explanation": "ADX=30.0"}}) == rg.TRENDING


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


def test_signal_regime_prefers_the_stored_first_class_field() -> None:
    """The money-path gate reads signals.regime (persisted at commit), not the
    factor prose — proven with a signal whose stored field DISAGREES with what its
    payload would recover. This is the whole point of the first-class field."""
    sig = _sig("ADX=22 moderate (20-25)")   # payload alone → transitional
    sig.regime = rg.TRENDING                 # but the durable field says trending
    assert regime_guard.signal_regime(sig) == rg.TRENDING
    assert regime_guard.is_eligible(sig) is True                    # trusts the field
    assert regime_guard.order_block_reason(sig, "active") is None


def test_signal_regime_falls_back_when_field_unset() -> None:
    """Legacy rows (regime column NULL) still gate via on-the-fly recovery."""
    sig = _sig("ADX=22 moderate (20-25)")
    assert sig.regime is None
    assert regime_guard.signal_regime(sig) == rg.TRANSITIONAL
    assert regime_guard.is_eligible(sig) is False


# --------------------------------------------------------------------------- #
# shadow measurement                                                          #
# --------------------------------------------------------------------------- #


def _row(
    status: str,
    adx: float,
    *,
    rr: float | None = None,
    day: int = 0,
    regime: str | None = None,
) -> Row:
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
        regime=regime,
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


def test_measure_buckets_by_the_stored_gate_regime_not_the_raw_level() -> None:
    """CANARY: the shadow must partition by the SAME persisted regime the active
    gate enforces (`Row.regime` ← signals.regime), not by re-bucketing the parsed
    ADX number — else forward evidence would mis-predict the gate at a band edge.
    Both rows have raw adx=30 (→ trending → both KEPT under raw bucketing), but one
    carries a stored TRANSITIONAL regime; only stored-regime bucketing kills it."""
    rows = [
        _row("sl_first", 30.0, regime=rg.TRANSITIONAL, day=0),
        _row("sl_first", 30.0, regime=rg.TRENDING, day=1),
    ]
    res = measure(rows)
    assert res.gated.trades == 1   # raw-adx bucketing would keep BOTH (fails on old code)
    assert res.killed.trades == 1  # the stored-TRANSITIONAL row is suppressed


def test_measure_falls_back_to_raw_level_when_regime_unset() -> None:
    """Rows without a stored regime (e.g. backtest rows) still bucket by the raw
    adx level — preserving prior behaviour and keeping the fallback path live."""
    res = measure([_row("sl_first", 22.0, day=0)])  # no regime → adx 22 → transitional
    assert res.killed.trades == 1
    assert res.gated.trades == 0


# --------------------------------------------------------------------------- #
# forward-evidence readiness (the flip's data gate + the daily reminder)       #
# --------------------------------------------------------------------------- #


def _rows(regime: str, status: str, n: int, *, rr: float | None = None, start_day: int = 0):
    return [_row(status, 30.0, rr=rr, day=start_day + i, regime=regime) for i in range(n)]


def test_forward_evidence_not_ready_below_target_n() -> None:
    ready, reason = forward_evidence_ready(measure(_rows(rg.TRANSITIONAL, "sl_first", 5)))
    assert ready is False
    assert "5/20" in reason


def test_forward_evidence_not_ready_when_suppressed_set_is_positive() -> None:
    # 20 suppressed WINS → the live tape disagrees with the backtest → do NOT flip
    ready, reason = forward_evidence_ready(measure(_rows(rg.TRANSITIONAL, "tp_first", 20, rr=2.0)))
    assert ready is False
    assert "not net-negative" in reason


def test_forward_evidence_ready_when_bar_met() -> None:
    # 20 suppressed losses (net-negative) + kept winners so gating lifts expectancy
    rows = _rows(rg.TRANSITIONAL, "sl_first", 20) + _rows(
        rg.TRENDING, "tp_first", 5, rr=2.0, start_day=100
    )
    ready, reason = forward_evidence_ready(measure(rows))
    assert ready is True
    assert "READY" in reason


def test_readiness_line_carries_tag_and_review_date() -> None:
    line = readiness_line(measure(_rows(rg.TRANSITIONAL, "sl_first", 3)))
    assert "NOT READY" in line
    assert FORWARD_EVIDENCE_REVIEW_DATE.isoformat() in line
