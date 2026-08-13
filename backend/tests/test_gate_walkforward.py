"""Unit tests for the §8 regime-gate walk-forward (Phase 6).

Pure over synthetic Rows — no DB, no tradecore wheel. Metrics are hand-computed
so a formula regression fails here, not silently in a report."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.entry_attribution import Row, realized_r
from app.services.gate_walkforward import (
    TRANSITIONAL_REGIME,
    GateMetrics,
    _max_drawdown_r,
    fold_consistency,
    gate_metrics,
    negative_regimes,
    render_markdown,
    run,
    time_folds,
    walk_forward_oos,
)

BASE = datetime(2026, 1, 1, tzinfo=UTC)

# ADX levels that land squarely in each regime bucket.
CHOPPY, TRANSITIONAL, TRENDING = 10.0, 22.0, 30.0


def mkrow(
    *,
    status: str = "sl_first",
    rr: float | None = None,
    adx: float | None = TRENDING,
    mfe_r: float | None = None,
    day: int = 0,
    direction: str = "BUY",
    confidence: int = 75,
) -> Row:
    return Row(
        status=status,
        mfe_r=mfe_r,
        mae_r=None,
        rr=rr,
        confidence=confidence,
        adx=adx,
        direction=direction,
        setup="t",
        created_at=BASE + timedelta(days=day),
        timeframe="1d",
        factors={},
    )


def many(n: int, first_day: int, last_day: int, **kw: object) -> list[Row]:
    """n rows cycling over the inclusive day range so every day is populated."""
    span = last_day - first_day + 1
    return [mkrow(day=first_day + (j % span), **kw) for j in range(n)]  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# realized_r — the shared expectancy unit                                     #
# --------------------------------------------------------------------------- #


def test_realized_r_by_status() -> None:
    assert realized_r(mkrow(status="tp_first", rr=2.0)) == 2.0
    assert realized_r(mkrow(status="tp_first", rr=None)) is None  # win, undefined RR → dropped
    assert realized_r(mkrow(status="sl_first")) == -1.0
    assert realized_r(mkrow(status="expired_open")) is None
    assert realized_r(mkrow(status="expired_untouched")) is None


def test_realized_r_winsorizes_tiny_sl_wins() -> None:
    # RR of 228 (a near-zero-risk artifact) is capped at the ±10R winsor bound.
    assert realized_r(mkrow(status="tp_first", rr=228.0)) == 10.0


# --------------------------------------------------------------------------- #
# gate_metrics                                                                #
# --------------------------------------------------------------------------- #


def test_gate_metrics_hand_computed() -> None:
    rows = [
        mkrow(status="tp_first", rr=2.0, mfe_r=2.5, day=0),
        mkrow(status="sl_first", mfe_r=0.3, day=1),
        mkrow(status="tp_first", rr=1.0, mfe_r=1.2, day=2),
        mkrow(status="sl_first", mfe_r=0.0, day=3),
        mkrow(status="expired_open", mfe_r=0.8, day=4),  # not decided, no realized R
    ]
    m = gate_metrics(rows)
    assert m.trades == 5
    assert m.decided == 4
    assert m.win_rate == pytest.approx(0.5)
    # realized R series = [2, -1, 1, -1] → total 1, mean 0.25
    assert m.total_r == pytest.approx(1.0)
    assert m.mean_exp_r == pytest.approx(0.25)
    # sample stdev of [2,-1,1,-1] = 1.5 → sharpe 0.25/1.5
    assert m.sharpe == pytest.approx(0.25 / 1.5)
    # daily curve [2,-1,1,-1]: peak 2, trough 1 → maxDD 1
    assert m.max_dd_r == pytest.approx(1.0)
    # reach1R over the 5 measured MFEs: 2.5 and 1.2 clear +1R → 2/5
    assert m.reach_1r == pytest.approx(0.4)


def test_gate_metrics_empty() -> None:
    m = gate_metrics([])
    assert m == GateMetrics(0, 0, None, None, 0.0, None, None, None)


def test_max_drawdown_r() -> None:
    assert _max_drawdown_r([]) == 0.0
    assert _max_drawdown_r([1.0, 2.0, 3.0]) == 0.0          # monotonic up
    assert _max_drawdown_r([-1.0, -1.0]) == 2.0             # first day draws down from 0 start
    assert _max_drawdown_r([5.0, -3.0, 1.0, -4.0]) == 6.0   # peak 5 → trough -1


# --------------------------------------------------------------------------- #
# time_folds                                                                  #
# --------------------------------------------------------------------------- #


def test_time_folds_contiguous_and_intact() -> None:
    rows = [mkrow(day=d) for d in range(10)]
    folds = time_folds(rows, 5)
    assert len(folds) == 5
    assert [len(f) for f in folds] == [2, 2, 2, 2, 2]
    # chronological, non-overlapping
    maxs = [max(r.created_at for r in f) for f in folds]
    mins = [min(r.created_at for r in f) for f in folds]
    assert all(maxs[i] < mins[i + 1] for i in range(4))


def test_time_folds_keeps_a_day_whole() -> None:
    # Three trades on day 0, one each on days 1..4; a day must not split across folds.
    rows = [mkrow(day=0), mkrow(day=0), mkrow(day=0)] + [mkrow(day=d) for d in range(1, 5)]
    folds = time_folds(rows, 5)
    day0_folds = {i for i, f in enumerate(folds) for r in f if r.created_at == BASE}
    assert len(day0_folds) == 1


def test_time_folds_clamps_k_to_days() -> None:
    rows = [mkrow(day=0), mkrow(day=1)]
    assert len(time_folds(rows, 5)) == 2  # only 2 distinct days
    assert time_folds([], 5) == []


# --------------------------------------------------------------------------- #
# negative_regimes — the "learn" step                                         #
# --------------------------------------------------------------------------- #


def test_negative_regimes_respects_floor_and_sign() -> None:
    rows = (
        many(24, 0, 4, status="sl_first", adx=TRANSITIONAL)          # 24 losses, negative, n≥20
        + many(24, 0, 4, status="tp_first", rr=1.0, adx=TRENDING)    # 24 wins, positive
        + many(10, 0, 4, status="sl_first", adx=CHOPPY)              # negative but n=10 < floor
    )
    learned = negative_regimes(rows)
    assert learned == {TRANSITIONAL_REGIME}  # trending positive; choppy below floor → not learned


def test_transitional_label_matches_canon() -> None:
    assert TRANSITIONAL_REGIME == "transitional (20–25)"


# --------------------------------------------------------------------------- #
# fold_consistency                                                            #
# --------------------------------------------------------------------------- #


def test_fold_consistency_flags_variant_win() -> None:
    # Each fold: transitional stops out (drags baseline), trending wins. Skipping
    # transitional must lift expectancy in every fold.
    rows: list[Row] = []
    for fold_start in (0, 5):
        rows += many(6, fold_start, fold_start + 4, status="sl_first", adx=TRANSITIONAL)
        rows += many(6, fold_start, fold_start + 4, status="tp_first", rr=1.0, adx=TRENDING)
    fcs = fold_consistency(rows, 2)
    assert len(fcs) == 2
    for fc in fcs:
        assert fc.variant_wins
        assert fc.variant.trades < fc.baseline.trades  # transitional removed


# --------------------------------------------------------------------------- #
# walk_forward_oos — learn on past, apply to unseen fold                       #
# --------------------------------------------------------------------------- #


def test_walk_forward_oos_learns_then_gates() -> None:
    # Fold 0 (train): transitional clearly negative with n≥floor. Fold 1 (test):
    # transitional negative, trending positive. The gate learned from fold 0 must
    # remove fold 1's transitional and lift its expectancy — all out-of-sample.
    train = many(24, 0, 4, status="sl_first", adx=TRANSITIONAL) + many(
        24, 0, 4, status="tp_first", rr=1.0, adx=TRENDING
    )
    test = many(4, 5, 9, status="sl_first", adx=TRANSITIONAL) + many(
        4, 5, 9, status="tp_first", rr=1.0, adx=TRENDING
    )
    oos = walk_forward_oos(train + test, 2)
    assert len(oos.folds) == 1  # only fold 1 is testable (fold 0 has no train)
    f = oos.folds[0]
    assert f.learned_skip == {TRANSITIONAL_REGIME}
    assert f.train_n == 48
    # baseline test: 4 wins + 4 losses → total 0; gated: 4 wins only → +4
    assert f.baseline.total_r == pytest.approx(0.0)
    assert f.gated.total_r == pytest.approx(4.0)
    assert f.gated.mean_exp_r == pytest.approx(1.0)
    assert f.gated.trades == 4
    # aggregate OOS mirrors the single test fold
    assert oos.gated.mean_exp_r > oos.baseline.mean_exp_r


def test_walk_forward_oos_learns_nothing_when_all_positive() -> None:
    rows = many(24, 0, 4, status="tp_first", rr=1.0, adx=TRANSITIONAL) + many(
        24, 5, 9, status="tp_first", rr=1.0, adx=TRANSITIONAL
    )
    oos = walk_forward_oos(rows, 2)
    assert oos.folds[0].learned_skip == set()
    # nothing skipped → gated == baseline
    assert oos.gated.total_r == pytest.approx(oos.baseline.total_r)


# --------------------------------------------------------------------------- #
# run + render smoke                                                          #
# --------------------------------------------------------------------------- #


def test_run_and_render_smoke() -> None:
    rows = (
        many(30, 0, 9, status="sl_first", adx=TRANSITIONAL, mfe_r=0.2)
        + many(30, 0, 9, status="tp_first", rr=2.0, adx=TRENDING, mfe_r=2.5)
    )
    result = run(rows, 5)
    md = render_markdown(result, day=BASE.date())
    assert "Regime-gate §8 walk-forward" in md
    assert "§8 change gate" in md
    assert "Anchored walk-forward (out-of-sample)" in md
    assert "## Verdict" in md
    # transitional is negative here → the proposed gate must beat baseline expectancy
    assert result.proposed.mean_exp_r > result.baseline.mean_exp_r
