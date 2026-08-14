"""Weight-retune experiment (Phase 6 slice 6.4) — group-weight coordinate sweep.

The 6.2 per-factor attribution said some factors predict edge (RSI_DIVERGENCE,
ADX, MORNING_STAR) and some hurt (DARK_CLOUD_COVER, EVENING_STAR, MACD_CROSS,
RSI_LEVEL). But the only weight lever the engine exposes is per-GROUP
(`app/backtest/engine.py::apply_weight_multipliers`), and the groups MIX helping
and hurting factors (momentum = RSI_DIVERGENCE + MACD_CROSS + RSI_LEVEL; pattern =
MORNING_STAR + DARK_CLOUD_COVER + EVENING_STAR + engulfings). So the per-factor
finding is not directly actionable, and theorising the multiplier→outcome mapping
is exactly the overfit trap the plan warns of. This experiment therefore MEASURES:
scale one group at a time (×0.5 / ×1.5) over the parity-clean corpus and score each
config on the §8 metrics + per-fold consistency, so a retune is chosen on evidence.

Read-only: group multipliers are applied inside the frozen scorer (byte-identical
to frozen when empty — the existing profile mechanism), the engine is untouched,
and nothing is promoted. Committing a retune to live scoring is a separate,
forward-evidence + sign-off gated step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.entry_attribution import Row
from app.services.gate_walkforward import DEFAULT_FOLDS, GateMetrics, gate_metrics

# The six confluence weight-groups (app/backtest/engine.py). "pattern" is
# tag-based (all candlestick patterns); the rest are name-based.
SWEEP_GROUPS = ["trend", "momentum", "volume", "structure", "pattern", "institutional"]
SWEEP_MULTS = (0.5, 1.5)

# All six groups are cross-engine consistent, so a corpus (Rust) sweep reproduces
# via a Python-path retune. A SCORING DOW_TREND is tagged ["structure"]
# (analysis/structure/dow.py), and Python _factor_group checks tags before names, so
# it groups "structure" — matching the Rust engine. (The _GROUP_NAMES "trend" entry is
# dead code for DOW_TREND; only a non-scoring/score-0 DOW_TREND falls through to it,
# which is immaterial.) An earlier "engine-specific" caveat here was based on the
# tagless case and was withdrawn 2026-08-14 — see dow-trend-grouping-gotcha in memory.


def sweep_configs() -> list[tuple[str, dict[str, float]]]:
    """(label, group-multipliers) for the coordinate sweep: baseline + each group
    scaled up and down one at a time (marginal effect, not a fragmenting full grid
    — a grid over 6 groups overfits ~800 corpus trades)."""
    configs: list[tuple[str, dict[str, float]]] = [("baseline", {})]
    for group in SWEEP_GROUPS:
        for mult in SWEEP_MULTS:
            configs.append((f"{group} ×{mult}", {group: mult}))
    return configs


def fold_bounds(rows: list[Row], k: int = DEFAULT_FOLDS) -> list[date]:
    """The k−1 cut dates that split the baseline's trading days into k contiguous
    folds. Shared across configs so every config is bucketed by the SAME time
    boundaries — a config trades a different set within each period, but the
    periods themselves are identical, making per-fold comparison apples-to-apples."""
    days = sorted({r.created_at.date() for r in rows})
    if len(days) < 2:
        return []
    k = max(1, min(k, len(days)))
    return [days[i * len(days) // k] for i in range(1, k)]


def bucket_by_bounds(rows: list[Row], cuts: list[date]) -> list[list[Row]]:
    """Bucket rows into len(cuts)+1 chronological folds by shared cut dates."""
    folds: list[list[Row]] = [[] for _ in range(len(cuts) + 1)]
    for r in rows:
        d = r.created_at.date()
        idx = sum(1 for c in cuts if d >= c)
        folds[idx].append(r)
    return folds


@dataclass(frozen=True)
class ConfigResult:
    label: str
    multipliers: dict[str, float]
    metrics: GateMetrics                    # whole corpus, this config's trade set
    fold_exp_r: list[float | None]          # per-fold mean expectancy (shared time folds)
    folds_beating_baseline: int             # of the folds where both are defined
    folds_compared: int


def evaluate(
    label: str,
    multipliers: dict[str, float],
    rows: list[Row],
    cuts: list[date],
    baseline_fold_exp_r: list[float | None],
) -> ConfigResult:
    """Whole-corpus §8 metrics for this config, plus how many shared time folds it
    beats the baseline's expectancy in. This is a per-fold TEMPORAL-CONSISTENCY
    proxy — NOT out-of-sample: the multiplier is applied to the whole corpus
    including each scored fold (no train/test split; contrast the anchored
    walk-forward in gate_walkforward). An aggregate win absent period-by-period is
    a likely artifact."""
    fold_exp_r = [gate_metrics(f).mean_exp_r for f in bucket_by_bounds(rows, cuts)]
    wins = 0
    compared = 0
    for cfg, base in zip(fold_exp_r, baseline_fold_exp_r, strict=True):
        if cfg is not None and base is not None:
            compared += 1
            if cfg > base:
                wins += 1
    return ConfigResult(
        label=label,
        multipliers=multipliers,
        metrics=gate_metrics(rows),
        fold_exp_r=fold_exp_r,
        folds_beating_baseline=wins,
        folds_compared=compared,
    )


@dataclass(frozen=True)
class RetuneReport:
    folds: int
    baseline: ConfigResult
    configs: list[ConfigResult] = field(default_factory=list)  # non-baseline, ranked


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #


def _f(x: float | None, spec: str = "+.3f") -> str:
    return format(x, spec) if x is not None else "—"


def _pct(x: float | None) -> str:
    return f"{x:.0%}" if x is not None else "—"


def _row(c: ConfigResult, base: GateMetrics) -> str:
    m = c.metrics
    me, be = m.mean_exp_r, base.mean_exp_r
    d_exp = None if (me is None or be is None) else me - be
    return (
        f"| {c.label} | {m.trades} | {_pct(m.win_rate)} | {_f(m.sharpe)} | "
        f"{_f(m.max_dd_r, '.1f')} | {_f(m.total_r, '+.1f')} | {_f(m.mean_exp_r)} | "
        f"{_f(d_exp)} | {c.folds_beating_baseline}/{c.folds_compared} |"
    )


def render_markdown(report: RetuneReport, *, day: date) -> str:
    b = report.baseline.metrics
    out: list[str] = [
        f"# Weight-retune experiment (6.4) — {day}",
        "",
        "_Read-only coordinate sweep over the Nifty50 daily corpus (parity-pinned "
        "`run_universe`, gate-70): each confluence weight-group scaled ×0.5 / ×1.5 one "
        "at a time. Group multipliers apply inside the frozen scorer (byte-identical to "
        "frozen when empty); the engine is untouched and nothing is promoted. `Δexp` = "
        f"mean-expectancy change vs baseline; `folds+` = of {report.folds} shared time "
        "folds, how many this config beats baseline expectancy in (a per-fold "
        "temporal-consistency proxy — NOT out-of-sample; no train/test split)._",
        "",
        "_Note: the 6.2 leak is per-FACTOR but this lever is per-GROUP, and groups mix "
        "helping and hurting factors — so a group that nets flat can still hide a real "
        "per-factor signal. A clean win here is actionable; a null result argues for "
        "per-factor weights (a larger, frozen-engine change) rather than group tuning._",
        "",
        "| config | trades | win% | Sharpe | maxDD R | total-R | mean expR | Δexp | folds+ |",
        "|---|--:|--:|--:|--:|--:|--:|--:|:-:|",
        _row(report.baseline, b),
    ]
    for c in report.configs:
        out.append(_row(c, b))
    out.append("")

    # Verdict: a config must beat baseline on BOTH total-R and expectancy AND hold in
    # a majority of folds to be worth promoting-in-shadow.
    def _promotable(c: ConfigResult) -> bool:
        m = c.metrics
        return (
            m.mean_exp_r is not None
            and b.mean_exp_r is not None
            and m.mean_exp_r > b.mean_exp_r
            and m.total_r > b.total_r
            and c.folds_compared > 0
            and c.folds_beating_baseline > c.folds_compared // 2
        )

    winners = [c for c in report.configs if _promotable(c)]
    if winners:
        lead = winners[0]  # configs arrive ranked by total-R
        verdict = (
            f"**{lead.label}** leads: expR "
            f"{b.mean_exp_r:+.3f}→{lead.metrics.mean_exp_r:+.3f}, total-R "
            f"{b.total_r:+.1f}→{lead.metrics.total_r:+.1f}, beats baseline in "
            f"{lead.folds_beating_baseline}/{lead.folds_compared} folds. Candidate for a "
            "shadow retune profile — NOT promoted here; that needs forward evidence + sign-off. "
            "Best-of-12 selected on the full corpus, so treat even this as in-sample until "
            "forward shadow confirms; `folds+` is the only guard against a lucky pick."
        )
    else:
        verdict = (
            "No single-group multiplier beats baseline on total-R AND expectancy AND a "
            "majority of folds. Group tuning does not cleanly capture the per-factor leak → "
            "the actionable lever is per-factor weights (a larger, frozen-engine change), not "
            "group weights. Do not promote a group retune here."
        )
    out += ["## Verdict", "", verdict, ""]
    return "\n".join(out) + "\n"
