"""Weight-retune experiment (Phase 6 slice 6.4) — pure sweep/fold/verdict logic.

No DB, no wheel: synthetic Rows with hand-computed fold outcomes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.entry_attribution import Row
from app.services.gate_walkforward import gate_metrics
from app.services.weight_retune import (
    SWEEP_GROUPS,
    ConfigResult,
    RetuneReport,
    bucket_by_bounds,
    evaluate,
    fold_bounds,
    render_markdown,
    sweep_configs,
)

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def mkrow(status: str, *, rr: float | None = None, day: int = 0) -> Row:
    return Row(
        status=status,
        mfe_r=None,
        mae_r=None,
        rr=rr,
        confidence=75,
        adx=30.0,
        direction="BUY",
        setup="t",
        created_at=BASE + timedelta(days=day),
        timeframe="1d",
        factors={},
    )


def test_sweep_configs_shape() -> None:
    configs = sweep_configs()
    assert configs[0] == ("baseline", {})
    # baseline + each of 6 groups at 2 multipliers
    assert len(configs) == 1 + len(SWEEP_GROUPS) * 2
    # every group appears scaled up and down exactly once
    for g in SWEEP_GROUPS:
        mults = sorted(m[g] for _, m in configs if g in m)
        assert mults == [0.5, 1.5]
    # each non-baseline config scales exactly one group
    assert all(len(m) == 1 for label, m in configs if label != "baseline")


def test_fold_bounds_and_bucket_are_shared_and_total() -> None:
    rows = [mkrow("sl_first", day=d) for d in range(10)]
    cuts = fold_bounds(rows, 5)
    assert len(cuts) == 4  # k-1
    folds = bucket_by_bounds(rows, cuts)
    assert len(folds) == 5
    assert sum(len(f) for f in folds) == len(rows)  # every row placed once
    # chronological: each fold's max day < next fold's min day
    maxs = [max((r.created_at for r in f), default=BASE) for f in folds]
    mins = [min((r.created_at for r in f), default=BASE) for f in folds]
    assert all(maxs[i] <= mins[i + 1] for i in range(4))


def test_bucket_uses_baseline_cuts_for_a_different_config() -> None:
    # A config that trades a DIFFERENT day-set is still bucketed by the shared cuts.
    base = [mkrow("sl_first", day=d) for d in range(10)]
    cuts = fold_bounds(base, 2)  # one cut at day 5
    cfg_rows = [mkrow("tp_first", rr=1.0, day=d) for d in (0, 1, 9)]  # sparse
    folds = bucket_by_bounds(cfg_rows, cuts)
    assert len(folds) == 2
    assert len(folds[0]) == 2 and len(folds[1]) == 1  # days 0,1 → fold0; day 9 → fold1


def test_evaluate_counts_fold_wins() -> None:
    # 2 folds: config wins fold 0 (all +1R) and loses fold 1 (all -1R) vs a flat baseline.
    rows = [mkrow("tp_first", rr=1.0, day=d) for d in range(5)] + [
        mkrow("sl_first", day=d) for d in range(5, 10)
    ]
    cuts = fold_bounds(rows, 2)
    res = evaluate("structure ×1.5", {"structure": 1.5}, rows, cuts, [0.0, 0.0])
    assert res.folds_compared == 2
    assert res.folds_beating_baseline == 1          # fold0 +1 > 0; fold1 -1 < 0
    assert res.metrics.trades == 10
    assert res.fold_exp_r[0] == 1.0 and res.fold_exp_r[1] == -1.0


def test_evaluate_skips_folds_with_no_baseline() -> None:
    rows = [mkrow("tp_first", rr=1.0, day=d) for d in range(4)]
    cuts = fold_bounds(rows, 2)
    # baseline undefined in fold 1 → that fold is not compared
    res = evaluate("x", {"trend": 0.5}, rows, cuts, [0.0, None])
    assert res.folds_compared == 1
    assert res.folds_beating_baseline == 1


def _cfg(
    label: str,
    rows: list[Row],
    fold_exp: list[float | None],
    wins: int,
    cmp: int,
    mult: dict[str, float] | None = None,
) -> ConfigResult:
    return ConfigResult(label, mult or {"pattern": 0.5}, gate_metrics(rows), fold_exp, wins, cmp)


def test_render_flags_a_winner() -> None:
    base_rows = [mkrow("tp_first", rr=1.0, day=0), mkrow("sl_first", day=1)]  # expR 0, totalR 0
    win_rows = [mkrow("tp_first", rr=1.0, day=0), mkrow("tp_first", rr=1.0, day=1)]  # expR +1
    report = RetuneReport(
        folds=2,
        baseline=ConfigResult("baseline", {}, gate_metrics(base_rows), [0.0, 0.0], 0, 0),
        configs=[_cfg("pattern ×0.5", win_rows, [1.0, 1.0], 2, 2)],
    )
    md = render_markdown(report, day=BASE.date())
    assert "Weight-retune experiment" in md
    assert "pattern ×0.5** leads" in md


def test_render_no_winner() -> None:
    base_rows = [mkrow("tp_first", rr=1.0, day=0), mkrow("tp_first", rr=1.0, day=1)]  # expR +1
    lose_rows = [mkrow("sl_first", day=0), mkrow("sl_first", day=1)]  # expR -1
    report = RetuneReport(
        folds=2,
        baseline=ConfigResult("baseline", {}, gate_metrics(base_rows), [1.0, 1.0], 0, 0),
        configs=[_cfg("trend ×0.5", lose_rows, [-1.0, -1.0], 0, 2, {"trend": 0.5})],
    )
    md = render_markdown(report, day=BASE.date())
    assert "per-factor weights" in md  # the null-result verdict


def test_render_names_the_top_ranked_winner() -> None:
    # With multiple promotable configs, the verdict names the top-ranked one
    # (configs arrive sorted by total-R). All groups are cross-engine consistent,
    # so there is no ‡ engine-specific caveat.
    base = [mkrow("tp_first", rr=1.0, day=0), mkrow("sl_first", day=1)]  # expR 0
    top = [mkrow("tp_first", rr=1.0, day=d) for d in range(6)]           # total +6
    second = [mkrow("tp_first", rr=1.0, day=d) for d in range(3)]        # total +3
    report = RetuneReport(
        folds=2,
        baseline=ConfigResult("baseline", {}, gate_metrics(base), [0.0, 0.0], 0, 0),
        configs=[  # pre-sorted by total-R desc, as the script emits
            _cfg("structure ×0.5", top, [1.0, 1.0], 2, 2, {"structure": 0.5}),
            _cfg("momentum ×1.5", second, [1.0, 1.0], 2, 2, {"momentum": 1.5}),
        ],
    )
    md = render_markdown(report, day=BASE.date())
    assert "structure ×0.5** leads" in md
    assert "‡" not in md
