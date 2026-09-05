"""§8 walk-forward regression for the regime gate (Phase 6).

The gate experiment (`scripts/gate_experiment.py`) showed, over the WHOLE Nifty50
daily corpus, that skipping the transitional ADX regime (20–25) roughly doubles
captured R. Two things kept that from being a §8-grade result:

  1. It reported total-R and expectancy but NOT the three metrics
     `docs/SIGNAL_ENGINE.md` §8 actually gates a merge-approval on —
     **win rate, Sharpe, and max drawdown**.
  2. The "skip transitional" rule was *derived* from the same corpus it was then
     scored on. Removing the cells you already labelled worst is circular; the
     honest question is whether a rule learned from the PAST improves the FUTURE.

This module answers both, read-only and pure over `list[Row]`:

  * `gate_metrics(rows)`     — the §8 metrics for one trade population.
  * `fold_consistency(...)`  — the fixed "skip transitional" rule scored inside
                               each sequential time fold: is the edge in every
                               period, or one lucky stretch?
  * `walk_forward_oos(...)`  — anchored walk-forward: on each expanding past
                               window LEARN which regimes are negative-expectancy
                               (only where n ≥ RANK_FLOOR — the honest ranking
                               floor), then apply that skip-set to the NEXT unseen
                               fold and accumulate. The out-of-sample answer.

No engine change; the corpus is the parity-pinned tradecore backtest. Never feeds
scoring/sizing/gating — this is measurement that argues FOR a change a human then
signs off on.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from app.core.ratios import WINSOR_R
from app.services.entry_attribution import RANK_FLOOR, Row, _regime_bucket, realized_r

# The exact label `_regime_bucket` emits for ADX 20–25, derived from the canon so
# it can never drift out of sync with the bucketing function.
TRANSITIONAL_REGIME = _regime_bucket(22.5)

DEFAULT_FOLDS = 5
SIGNIFICANT_CHANGE = 0.05  # §8: a >5% move in win rate / Sharpe / maxDD needs sign-off


@dataclass(frozen=True)
class GateMetrics:
    """§8 outcome metrics for one trade population. `total_r`, `mean_exp_r`,
    `sharpe` and `max_dd_r` are over the realized-R series (decided trades with a
    defined R — see `realized_r`); `win_rate` and counts use all decided trades;
    `reach_1r` is over rows with a measured MFE.

    Granularity is mixed BY DESIGN: `sharpe`/`mean_exp_r`/`total_r` are per-trade,
    while `max_dd_r` is over the daily-aggregated curve (daily bars share a fill
    timestamp, so intraday trade order is arbitrary — aggregating per day removes
    that ambiguity). `total_r` is granularity-invariant (a sum); the other two are
    not the same series, so read Sharpe and drawdown as separate risk lenses."""

    trades: int
    decided: int
    win_rate: float | None
    mean_exp_r: float | None
    total_r: float
    sharpe: float | None       # per-trade: mean(R) / stdev(R) over the realized-R series
    max_dd_r: float | None     # worst peak-to-trough on the daily-aggregated equity curve, in R
    reach_1r: float | None


def _max_drawdown_r(daily_r: list[float]) -> float:
    """Worst peak-to-trough decline on the cumulative-R equity curve, in R.
    `daily_r` is per-day summed realized R in chronological order. Equity starts
    at 0 (peak seeded at 0), so a first losing day draws down from the start."""
    peak = 0.0
    equity = 0.0
    mdd = 0.0
    for x in daily_r:
        equity += x
        peak = max(peak, equity)
        mdd = max(mdd, peak - equity)
    return mdd


def gate_metrics(rows: list[Row]) -> GateMetrics:
    """The §8 metrics for one trade population. Drawdown is computed on a
    daily-aggregated equity curve (daily bars share a fill timestamp, so intraday
    trade order within a day is arbitrary — aggregating removes that ambiguity)."""
    decided = [r for r in rows if r.status in ("tp_first", "sl_first")]
    wins = sum(1 for r in decided if r.status == "tp_first")

    # Realized-R series with its trading day, for total/mean/Sharpe/drawdown.
    dated_r = [(r.created_at.date(), rr) for r in rows if (rr := realized_r(r)) is not None]
    rs = [rr for _, rr in dated_r]

    by_day: dict[date, float] = {}
    for d, rr in dated_r:
        by_day[d] = by_day.get(d, 0.0) + rr
    daily_curve = [by_day[d] for d in sorted(by_day)]

    stdev = statistics.stdev(rs) if len(rs) >= 2 else 0.0
    mfes = [r.mfe_r for r in rows if r.mfe_r is not None]
    reached = sum(1 for m in mfes if m >= 1.0)

    return GateMetrics(
        trades=len(rows),
        decided=len(decided),
        win_rate=(wins / len(decided)) if decided else None,
        mean_exp_r=statistics.fmean(rs) if rs else None,
        total_r=sum(rs),
        sharpe=(statistics.fmean(rs) / stdev) if rs and stdev > 0 else None,
        max_dd_r=_max_drawdown_r(daily_curve) if daily_curve else None,
        reach_1r=(reached / len(mfes)) if mfes else None,
    )


def _skip(rows: list[Row], regimes: set[str]) -> list[Row]:
    """Rows whose decision-bar regime is NOT in the skip-set."""
    return [r for r in rows if _regime_bucket(r.adx) not in regimes]


def time_folds(rows: list[Row], k: int = DEFAULT_FOLDS) -> list[list[Row]]:
    """Partition rows into `k` contiguous, chronological folds split on trading-day
    boundaries (a day is never split across folds). Folds may differ in size when
    days carry uneven trade counts; empty tail folds are dropped."""
    days = sorted({r.created_at.date() for r in rows})
    if not days:
        return []
    k = max(1, min(k, len(days)))
    fold_of_day = {d: min(k - 1, i * k // len(days)) for i, d in enumerate(days)}
    folds: list[list[Row]] = [[] for _ in range(k)]
    for r in rows:
        folds[fold_of_day[r.created_at.date()]].append(r)
    return [f for f in folds if f]


def _date_range(rows: list[Row]) -> tuple[date, date] | None:
    if not rows:
        return None
    ds = [r.created_at.date() for r in rows]
    return min(ds), max(ds)


def negative_regimes(rows: list[Row], *, floor: int = RANK_FLOOR) -> set[str]:
    """Regimes with negative mean realized R — but only where the realized-R
    sample (the series the mean is actually taken over — decided trades minus
    undefined-RR wins) clears `floor` (RANK_FLOOR): below it the mean is not
    reliable enough to rank, so the regime is never learned as a skip. This is
    what an expanding train window 'discovers' about which regime to avoid. On the
    corpus RR is always defined (risk > 0), so this equals the decided count."""
    by_regime: dict[str, list[float]] = {}
    for r in rows:
        rr = realized_r(r)
        if rr is not None:
            by_regime.setdefault(_regime_bucket(r.adx), []).append(rr)
    return {
        reg
        for reg, terms in by_regime.items()
        if len(terms) >= floor and statistics.fmean(terms) < 0
    }


@dataclass(frozen=True)
class FoldConsistency:
    """One sequential time fold: the fixed skip-transitional rule scored against
    baseline within that fold. `variant_wins` is on realized expectancy."""

    span: tuple[date, date] | None
    baseline: GateMetrics
    variant: GateMetrics

    @property
    def variant_wins(self) -> bool:
        b = self.baseline.mean_exp_r
        v = self.variant.mean_exp_r
        return b is not None and v is not None and v > b


def fold_consistency(rows: list[Row], k: int = DEFAULT_FOLDS) -> list[FoldConsistency]:
    """The FIXED 'skip transitional' rule scored inside each fold — shows whether
    the whole-corpus edge is present period-by-period or concentrated in one."""
    out: list[FoldConsistency] = []
    for fold in time_folds(rows, k):
        out.append(
            FoldConsistency(
                span=_date_range(fold),
                baseline=gate_metrics(fold),
                variant=gate_metrics(_skip(fold, {TRANSITIONAL_REGIME})),
            )
        )
    return out


@dataclass(frozen=True)
class OosFold:
    """One out-of-sample test fold in the anchored walk-forward: the skip-set was
    learned only from the folds BEFORE it, then applied here."""

    span: tuple[date, date] | None
    train_n: int
    learned_skip: set[str]
    baseline: GateMetrics   # the test fold, all regimes
    gated: GateMetrics      # the test fold with the learned skip-set removed


@dataclass(frozen=True)
class WalkForwardOos:
    folds: list[OosFold]
    baseline: GateMetrics   # all OOS test folds concatenated, all regimes
    gated: GateMetrics      # all OOS test folds concatenated, each with ITS learned skip-set


def walk_forward_oos(rows: list[Row], k: int = DEFAULT_FOLDS) -> WalkForwardOos:
    """Anchored (expanding-window) walk-forward. For each fold after the first,
    learn the negative-expectancy regimes from every earlier fold, apply that
    skip-set to this (unseen) fold, and accumulate. The aggregate compares what a
    strategy that learned the bad regime FROM HISTORY would have captured going
    forward against leaving every regime in."""
    folds = time_folds(rows, k)
    oos: list[OosFold] = []
    base_rows: list[Row] = []
    gated_rows: list[Row] = []
    for i in range(1, len(folds)):
        train = [r for f in folds[:i] for r in f]
        test = folds[i]
        skip = negative_regimes(train)
        gated_test = _skip(test, skip)
        oos.append(
            OosFold(
                span=_date_range(test),
                train_n=len(train),
                learned_skip=skip,
                baseline=gate_metrics(test),
                gated=gate_metrics(gated_test),
            )
        )
        base_rows.extend(test)
        gated_rows.extend(gated_test)
    return WalkForwardOos(
        folds=oos, baseline=gate_metrics(base_rows), gated=gate_metrics(gated_rows)
    )


@dataclass(frozen=True)
class WalkForwardResult:
    """Everything the report needs. `proposed` is the FIXED skip-transitional rule
    over the whole corpus (the change actually on the table); `oos` is the honest
    learned-from-history-applied-forward test of it."""

    total: int
    folds: int
    baseline: GateMetrics       # whole corpus, all regimes (what ships today)
    proposed: GateMetrics       # whole corpus, skip transitional (the proposed gate)
    consistency: list[FoldConsistency]
    oos: WalkForwardOos


def run(rows: list[Row], k: int = DEFAULT_FOLDS) -> WalkForwardResult:
    return WalkForwardResult(
        total=len(rows),
        folds=k,
        baseline=gate_metrics(rows),
        proposed=gate_metrics(_skip(rows, {TRANSITIONAL_REGIME})),
        consistency=fold_consistency(rows, k),
        oos=walk_forward_oos(rows, k),
    )


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #


def _f(x: float | None, spec: str = "+.3f") -> str:
    return format(x, spec) if x is not None else "—"


def _pct(x: float | None) -> str:
    return f"{x:.0%}" if x is not None else "—"


def _span(s: tuple[date, date] | None) -> str:
    return f"{s[0]} → {s[1]}" if s else "—"


def _rel_change(base: float | None, variant: float | None) -> float | None:
    """Relative change vs baseline (§8's '>5%' is on this). None when undefined."""
    if base is None or variant is None or base == 0:
        return None
    return (variant - base) / abs(base)


def _flag(rel: float | None) -> str:
    if rel is None:
        return "—"
    mark = " ⚠" if abs(rel) > SIGNIFICANT_CHANGE else ""
    return f"{rel:+.0%}{mark}"


_METRIC_HEADER = (
    "| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |"
)
_METRIC_SEP = "|---|--:|--:|--:|--:|--:|--:|--:|--:|"


def _metric_row(name: str, m: GateMetrics) -> str:
    return (
        f"| {name} | {m.trades} | {m.decided} | {_pct(m.win_rate)} | {_f(m.sharpe)} | "
        f"{_f(m.max_dd_r, '.1f')} | {_f(m.total_r, '+.1f')} | {_f(m.mean_exp_r)} | "
        f"{_pct(m.reach_1r)} |"
    )


def render_markdown(result: WalkForwardResult, *, day: date) -> str:
    b, p = result.baseline, result.proposed
    wr_ch = _flag(_rel_change(b.win_rate, p.win_rate))
    sh_ch = _flag(_rel_change(b.sharpe, p.sharpe))
    dd_ch = _flag(_rel_change(b.max_dd_r, p.max_dd_r))
    out: list[str] = [
        f"# Regime-gate §8 walk-forward — {day}",
        "",
        "_Read-only over the Nifty50 daily corpus (parity-pinned Rust `run_universe`, "
        "gate-70); NO engine change. Promotes the gate experiment into a §8-grade "
        "regression: the three metrics §8 gates a merge on (win rate, Sharpe, max "
        "drawdown) plus an out-of-sample test of the finding._",
        "",
        f"_Definitions: realized R = +RR (target) / −1R (stop), winsorized ±{WINSOR_R:.0f}R. "
        "Sharpe = mean(R)/stdev(R) per trade. maxDD = worst peak-to-trough on the "
        f"daily-aggregated R equity curve. Folds = {result.folds} contiguous time slices. "
        f"A regime is 'learned' as bad only with ≥{RANK_FLOOR} decided trades._",
        "",
        "## 1. Aggregate §8 metrics (whole corpus)",
        "",
        _METRIC_HEADER,
        _METRIC_SEP,
        _metric_row("baseline (all regimes)", b),
        _metric_row("proposed (skip transitional)", p),
        "",
        "**§8 change gate** — relative move vs baseline (⚠ = >5%, needs explicit sign-off):",
        "",
        "| metric | baseline | proposed | change |",
        "|---|--:|--:|--:|",
        f"| win rate | {_pct(b.win_rate)} | {_pct(p.win_rate)} | {wr_ch} |",
        f"| Sharpe | {_f(b.sharpe)} | {_f(p.sharpe)} | {sh_ch} |",
        f"| max drawdown (R) | {_f(b.max_dd_r, '.1f')} | {_f(p.max_dd_r, '.1f')} | {dd_ch} |",
        "",
    ]

    # Section 2 — fixed-rule consistency across folds.
    wins = sum(1 for fc in result.consistency if fc.variant_wins)
    out += [
        f"## 2. Fixed-rule consistency across {len(result.consistency)} time folds",
        "",
        "_Skip-transitional scored INSIDE each fold — is the edge everywhere or one stretch?_",
        "",
        "| fold | n (base→var) | win% (base→var) | total-R (base→var) "
        "| mean expR (base→var) | variant wins? |",
        "|---|--:|--:|--:|--:|:-:|",
    ]
    for fc in result.consistency:
        b2, v2 = fc.baseline, fc.variant
        out.append(
            f"| {_span(fc.span)} | {b2.trades}→{v2.trades} | "
            f"{_pct(b2.win_rate)}→{_pct(v2.win_rate)} | "
            f"{_f(b2.total_r, '+.1f')}→{_f(v2.total_r, '+.1f')} | "
            f"{_f(b2.mean_exp_r)}→{_f(v2.mean_exp_r)} | {'✓' if fc.variant_wins else '✗'} |"
        )
    out += ["", f"**Variant wins expectancy in {wins}/{len(result.consistency)} folds.**", ""]

    # Section 3 — anchored walk-forward (out-of-sample).
    oos = result.oos
    out += [
        "## 3. Anchored walk-forward (out-of-sample)",
        "",
        "_Learn the negative-expectancy regime(s) from every EARLIER fold, apply to the "
        "next unseen fold. Defeats the circularity: the skip is decided without seeing the "
        "fold it is scored on._",
        "",
        "| test fold | train n | learned skip | total-R (base→gated) "
        "| mean expR (base→gated) | win% (base→gated) |",
        "|---|--:|---|--:|--:|--:|",
    ]
    for f in oos.folds:
        skip = ", ".join(sorted(f.learned_skip)) if f.learned_skip else "(none)"
        out.append(
            f"| {_span(f.span)} | {f.train_n} | {skip} | "
            f"{_f(f.baseline.total_r, '+.1f')}→{_f(f.gated.total_r, '+.1f')} | "
            f"{_f(f.baseline.mean_exp_r)}→{_f(f.gated.mean_exp_r)} | "
            f"{_pct(f.baseline.win_rate)}→{_pct(f.gated.win_rate)} |"
        )
    out += [
        "",
        "**Aggregate out-of-sample (all test folds):**",
        "",
        _METRIC_HEADER,
        _METRIC_SEP,
        _metric_row("OOS baseline (all regimes)", oos.baseline),
        _metric_row("OOS learned-gate", oos.gated),
        "",
    ]

    # Verdict.
    holds = (
        oos.gated.mean_exp_r is not None
        and oos.baseline.mean_exp_r is not None
        and oos.gated.mean_exp_r > oos.baseline.mean_exp_r
        and wins > len(result.consistency) // 2  # strict majority of folds
    )
    verdict = (
        "HOLDS out-of-sample — the learned gate beats baseline expectancy on unseen folds "
        f"and skip-transitional wins the majority of time folds ({wins}/{len(result.consistency)})."
        if holds
        else "DOES NOT hold cleanly out-of-sample — treat the whole-corpus result with caution."
    )
    out += [
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "The §8 change gate above flags the win-rate / Sharpe / drawdown moves that exceed "
        "±5%: those require **explicit user sign-off** before the regime gate is implemented "
        "in the engine. This report is read-only evidence — it changes nothing.",
        "",
    ]
    return "\n".join(out) + "\n"
