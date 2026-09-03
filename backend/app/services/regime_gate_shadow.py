"""Regime-gate shadow measurement (Phase 6) — "measure before gating".

The §8 walk-forward validated the regime gate on the Nifty50 daily BACKTEST.
This checks the SAME rule forward on the LIVE tradeable cohort — real committed
signals with recorded outcomes — so the decision to flip the overlay
shadow→active rests on live evidence too, not only the backtest. It is the
measurement half of `app/signals/regime_guard.py`; it never suppresses anything.

Read-only: reuses `entry_attribution.load_attribution_rows` (the live cohort) and
`gate_walkforward.gate_metrics` (the §8 metrics), and the SAME `regime_guard.SKIP_REGIMES`
policy the gate enforces. Crucially it partitions each row by the SAME persisted
`signals.regime` the active gate reads (`Row.regime`, since 2026-08-14) — not by
re-bucketing the parsed ADX number — so the forward evidence measures exactly the set
the gate would suppress, with no band-edge divergence between measurement and enforcement.
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
from app.signals.eligibility import mode_banner


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


def _gate_regime(row: Row) -> str:
    """The regime the ACTIVE gate would enforce on this row — the persisted
    `signals.regime` carried on the row (identical to regime_guard.signal_regime),
    so the shadow measures exactly the gate's partition. Falls back to the raw-level
    bucket for rows with no stored regime (e.g. backtest rows), preserving the prior
    behaviour there."""
    return row.regime or rg.adx_regime(row.adx)


def measure(
    rows: list[Row],
    *,
    skip: frozenset[str] = regime_guard.SKIP_REGIMES,
    since: datetime = OUTCOME_EPOCH,
) -> RegimeGateShadow:
    kept = [r for r in rows if _gate_regime(r) not in skip]
    killed = [r for r in rows if _gate_regime(r) in skip]
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


# Forward-evidence bar for flipping the gate active (Phase 6). The §8 backtest
# already powered the decision (killed n=223); this live check only guards against
# the live tape behaving DIFFERENTLY, so the bar is the project's n=20 rank floor,
# not a re-powering. The accumulated live cohort already MET the bar (2026-08-14);
# the user's chosen path is "confirm stability, then flip" — REVIEW_DATE is the
# ~4-week window over which the READY verdict must HOLD (surfaced every `make
# analysis`) before the §8 sign-off + flip.
FORWARD_EVIDENCE_TARGET_N = 20
MODE_EFFECTIVE_FROM = date(2026, 9, 2)
"""When `regime_gate_mode` last changed — printed beside the mode in the report.

The mode is read at RENDER time while the cohort below spans weeks, so a report
generated after a flip would otherwise describe an earlier, differently-moded period
in the present tense. That is the same false-statement bug as the old hardcoded
"SHADOW: nothing is suppressed", just inverted (bug-hunter LOW, 2026-09-02): after the
09-02 revert this report would have claimed "nothing is suppressed" about the 88
resolved suppressed trades from the 08-14 -> 09-02 ACTIVE window — and this report is
the input to the keep/revert decision.

**Bump this on every mode flip.**
"""

FORWARD_EVIDENCE_REVIEW_DATE = date(2026, 9, 15)


def forward_evidence_ready(result: RegimeGateShadow) -> tuple[bool, str]:
    """Is there enough LIVE forward evidence to justify flipping the gate active?
    Bar (all three): ≥ FORWARD_EVIDENCE_TARGET_N resolved suppressed trades, the
    suppressed set net-negative, and gating lifting expectancy over baseline.
    Returns (ready, reason). This never flips anything — it is advice for the human
    §8 sign-off, which is a separate, required step."""
    k, g, b = result.killed, result.gated, result.baseline
    n = k.decided
    if n < FORWARD_EVIDENCE_TARGET_N:
        return False, f"{n}/{FORWARD_EVIDENCE_TARGET_N} resolved suppressed trades — keep accruing"
    if k.mean_exp_r is None or k.mean_exp_r >= 0:
        got = "—" if k.mean_exp_r is None else f"{k.mean_exp_r:+.3f}"
        return False, (
            f"{n} resolved suppressed trades but the suppressed set is not net-negative "
            f"({got} expR) — the live tape disagrees with the backtest; do NOT flip"
        )
    if b.mean_exp_r is not None and g.mean_exp_r is not None and g.mean_exp_r <= b.mean_exp_r:
        return False, (
            f"{n} resolved suppressed trades, but gating does not lift live expectancy "
            f"({b.mean_exp_r:+.3f}→{g.mean_exp_r:+.3f}) — do NOT flip"
        )
    return True, (
        f"{n} resolved suppressed trades, net-negative ({k.mean_exp_r:+.3f}); gating lifts "
        f"expectancy {b.mean_exp_r:+.3f}→{g.mean_exp_r:+.3f} — READY for §8 sign-off + flip"
    )


def readiness_line(result: RegimeGateShadow) -> str:
    """One-line status for the daily run's stdout (the passive reminder)."""
    ready, reason = forward_evidence_ready(result)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return (
        f"[regime-gate forward evidence] {tag} — {reason} "
        f"(review checkpoint {FORWARD_EVIDENCE_REVIEW_DATE.isoformat()})"
    )


def render_markdown(result: RegimeGateShadow, *, day: date, mode: str) -> str:
    """`mode` is the LIVE `regime_gate_mode`, printed in the preamble. It used to be
    hardcoded "SHADOW: nothing is suppressed", which was FALSE for the 19 days the gate
    ran active (2026-08-14 -> 2026-09-02) - see `eligibility.mode_banner`."""
    skip = ", ".join(sorted(result.skip)) or "(none)"
    out = [
        f"# Regime-gate shadow (live cohort) — {day}",
        "",
        f"_Read-only. What the regime overlay (skip: {skip}) WOULD do to the live "
        f"tradeable cohort since {result.since.date()} — the forward, live counterpart "
        f"to the §8 backtest (`gate-walkforward-*.md`). "
        f"{mode_banner(mode, since=MODE_EFFECTIVE_FROM.isoformat())} "
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
    _ready, _reason = forward_evidence_ready(result)
    out += [
        f"**Flip readiness:** {'✅ READY' if _ready else '⏳ NOT READY'} — {_reason}. Review "
        f"checkpoint {FORWARD_EVIDENCE_REVIEW_DATE.isoformat()} (the real trigger is the count, "
        "not the date); flipping also requires explicit user §8 sign-off.",
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
            f"suppressed set is net-negative ({k:+.3f}). See the **Flip readiness** line for the "
            "sign-off bar."
        )
    else:
        verdict = "Gating does not lift live expectancy yet — keep measuring before any flip."
    out += [f"**Verdict:** {verdict}", ""]
    return "\n".join(out) + "\n"
