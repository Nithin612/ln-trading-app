"""Regime-gate shadow measurement (Phase 6) — "measure before gating".

The §8 walk-forward validated the regime gate on the Nifty50 daily BACKTEST.
This checks the SAME rule forward on the LIVE tradeable cohort — real committed
signals with recorded outcomes — so the decision to flip the overlay
shadow→active rests on live evidence too, not only the backtest. It is the
measurement half of `app/signals/regime_guard.py`; it never suppresses anything.

Read-only: reuses `entry_attribution.load_attribution_rows` (the live cohort,
bucketed by the canonical regime) and `gate_walkforward.gate_metrics` (the §8
metrics), and the SAME `regime_guard.SKIP_REGIMES` policy the gate enforces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.entry_attribution import Row, load_attribution_rows
from app.services.gate_walkforward import GateMetrics, gate_metrics
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import regime as rg
from app.signals import regime_guard


@dataclass(frozen=True)
class RegimeGateShadow:
    """What the regime overlay would do to the live cohort. `gated` is the kept
    set (what would trade under an active gate); `killed` is the suppressed
    subset — shown so a positive-expectancy `killed` is an immediate red flag
    that the live tape disagrees with the backtest."""

    cohort: str
    since: datetime
    skip: frozenset[str]
    baseline: GateMetrics   # every live signal (what trades today)
    gated: GateMetrics      # kept — regime NOT in skip-set
    killed: GateMetrics     # suppressed — regime in skip-set


def measure(
    rows: list[Row],
    *,
    skip: frozenset[str] = regime_guard.SKIP_REGIMES,
    since: datetime = OUTCOME_EPOCH,
) -> RegimeGateShadow:
    kept = [r for r in rows if rg.adx_regime(r.adx) not in skip]
    killed = [r for r in rows if rg.adx_regime(r.adx) in skip]
    return RegimeGateShadow(
        cohort="tradeable",
        since=since,
        skip=skip,
        baseline=gate_metrics(rows),
        gated=gate_metrics(kept),
        killed=gate_metrics(killed),
    )


async def compute_regime_gate_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> RegimeGateShadow:
    """The live tradeable cohort (is_shadow FALSE) run through the gate policy."""
    rows = await load_attribution_rows(db, shadow=False, since=since)
    return measure(rows, since=since)


def _row(name: str, m: GateMetrics) -> str:
    def f(x: float | None, spec: str = "+.3f") -> str:
        return format(x, spec) if x is not None else "—"

    def pct(x: float | None) -> str:
        return f"{x:.0%}" if x is not None else "—"

    return (
        f"| {name} | {m.trades} | {m.decided} | {pct(m.win_rate)} | {f(m.sharpe)} | "
        f"{f(m.max_dd_r, '.1f')} | {f(m.total_r, '+.1f')} | {f(m.mean_exp_r)} | "
        f"{pct(m.reach_1r)} |"
    )


def render_markdown(result: RegimeGateShadow, *, day: date) -> str:
    skip = ", ".join(sorted(result.skip)) or "(none)"
    out = [
        f"# Regime-gate shadow (live cohort) — {day}",
        "",
        f"_Read-only. What the regime overlay (skip: {skip}) WOULD do to the live "
        f"tradeable cohort since {result.since.date()} — the forward, live counterpart "
        "to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. "
        "Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape "
        "disagrees with the backtest — do not flip to active._",
        "",
        "| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
        _row("baseline (all live signals)", result.baseline),
        _row("gated (kept — would trade)", result.gated),
        _row("killed (suppressed)", result.killed),
        "",
    ]
    b, g = result.baseline.mean_exp_r, result.gated.mean_exp_r
    k = result.killed.mean_exp_r
    if result.killed.decided == 0:
        verdict = (
            "No live decided trades fall in the skip-set yet — insufficient forward "
            "evidence; keep measuring."
        )
    elif k is not None and k > 0:
        verdict = (
            f"⚠ Suppressed trades are POSITIVE ({k:+.3f} expR) on the live tape — the backtest "
            "finding is NOT reproducing live. Do not flip to active."
        )
    elif b is not None and g is not None and g > b:
        verdict = (
            f"Consistent with the backtest: gating lifts live expectancy {b:+.3f}→{g:+.3f} and the "
            f"suppressed set is net-negative ({k:+.3f}). Keep accruing before flipping."
        )
    else:
        verdict = "Gating does not lift live expectancy yet — keep measuring before any flip."
    out += [f"**Verdict:** {verdict}", ""]
    return "\n".join(out) + "\n"
