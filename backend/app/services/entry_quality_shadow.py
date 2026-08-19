"""Entry-quality shadow measurement (Phase 6.8 R-track) — "measure before gating".

The forward, live counterpart to the one-off replay in
`docs/analysis/exit-ladder-research-2026-08-18.md`. Runs the entry-quality overlay
(`app/signals/entry_quality.py`) over the live TRADEABLE signal cohort and, for the
signals that were actually traded and closed, compares the FLAGGED set's realized
P&L to the PASSED set's — the same evidence the regime-gate shadow builds. Read-only.

Two checks, reported separately because they are moded/flipped separately:
  • diversity — ACTIVE (enforces the "≥2 factors" hard rule); reported for visibility.
  • sl_atr — SHADOW (a tunable threshold); its flagged-vs-passed expectancy is the
    forward evidence for an eventual flip, gated like the regime gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.signal import Signal
from app.models.trading import Position
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import entry_quality as eq
from app.trading.atr import atr_timeframe_for, latest_atr

# Forward-evidence bar for flipping sl_atr active — the project's n=20 rank floor.
FORWARD_EVIDENCE_TARGET_N = 20


@dataclass
class Bucket:
    n: int = 0  # signals in the bucket
    resolved: int = 0  # traded AND closed (a realized P&L exists)
    net: Decimal = field(default_factory=lambda: Decimal("0"))  # Σ realized of resolved
    wins: int = 0

    def add(self, realized: Decimal | None) -> None:
        self.n += 1
        if realized is not None:
            self.resolved += 1
            self.net += realized
            if realized > 0:
                self.wins += 1

    @property
    def avg(self) -> Decimal | None:
        return (self.net / self.resolved) if self.resolved else None

    @property
    def win_pct(self) -> int | None:
        return round(100 * self.wins / self.resolved) if self.resolved else None


@dataclass(frozen=True)
class EntryQualityShadow:
    since: datetime
    n_signals: int
    div_flagged: Bucket  # diversity check fired
    div_passed: Bucket
    sl_flagged: Bucket  # sl_atr check fired
    sl_passed: Bucket


async def _realized_by_signal(db: AsyncSession, signal_ids: list[str]) -> dict[str, Decimal]:
    """Σ realized P&L of each signal's CLOSED positions (reopen-safe), one query."""
    out: dict[str, Decimal] = {}
    if not signal_ids:
        return out
    for sig_id, realized, closed_at in (
        await db.execute(
            select(Position.signal_id, Position.realized_pnl, Position.closed_at).where(
                Position.signal_id.in_(signal_ids), Position.mode == "paper"
            )
        )
    ).all():
        if closed_at is not None and sig_id is not None:
            out[sig_id] = out.get(sig_id, Decimal("0")) + realized
    return out


async def compute_entry_quality_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> EntryQualityShadow:
    """Evaluate the tradeable signal cohort (is_shadow FALSE) since `since` and
    partition by each check's flag, with resolved outcomes."""
    sigs = (
        await db.execute(
            select(Signal).where(
                Signal.is_shadow.is_(False), Signal.created_at >= since
            )
        )
    ).scalars().all()
    realized = await _realized_by_signal(db, [s.id for s in sigs])

    div_f, div_p, sl_f, sl_p = Bucket(), Bucket(), Bucket(), Bucket()
    for s in sigs:
        atr = await latest_atr(
            db, s.stock_id, timeframe=atr_timeframe_for(s.classification), before=s.created_at
        )
        v = eq.evaluate(
            entry=Decimal(str(s.entry_price)),
            stop_loss=Decimal(str(s.stop_loss)),
            factor_scores=s.factor_scores,
            atr=atr,
            min_scoring_factors=settings.entry_min_scoring_factors,
            max_dominant_share=Decimal(str(settings.entry_max_dominant_factor_share)),
            min_sl_atr_mult=Decimal(str(settings.entry_min_sl_atr_mult)),
        )
        r = realized.get(s.id)
        (div_f if v.diversity_blocked else div_p).add(r)
        (sl_f if v.sl_blocked else sl_p).add(r)

    return EntryQualityShadow(
        since=since, n_signals=len(sigs),
        div_flagged=div_f, div_passed=div_p, sl_flagged=sl_f, sl_passed=sl_p,
    )


def sl_flip_ready(r: EntryQualityShadow) -> tuple[bool, str]:
    """Is there enough forward evidence to flip the sl_atr check active? Bar (all):
    ≥ N resolved flagged trades, the flagged set net-losing, AND worse than the
    passed set. Advice for the human sign-off — never flips anything."""
    f, p = r.sl_flagged, r.sl_passed
    if f.resolved < FORWARD_EVIDENCE_TARGET_N:
        return False, (
            f"{f.resolved}/{FORWARD_EVIDENCE_TARGET_N} resolved sl-flagged trades — keep accruing"
        )
    if f.avg is None or f.avg >= 0:
        return False, f"sl-flagged set is not net-negative ({f.avg}) — do NOT flip"
    if p.avg is not None and f.avg >= p.avg:
        return False, f"sl-flagged ({f.avg}) not worse than passed ({p.avg}) — do NOT flip"
    return True, (
        f"sl-flagged net-negative ({f.avg}), worse than passed ({p.avg}) — READY for sign-off"
    )


def readiness_line(r: EntryQualityShadow) -> str:
    ready, reason = sl_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[entry-quality sl_atr forward evidence] {tag} — {reason}"


def _row(name: str, b: Bucket) -> str:
    avg = f"₹{b.avg:,.0f}" if b.avg is not None else "—"
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    net = f"₹{b.net:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | {net} | {avg} | {win} |"


def render_markdown(r: EntryQualityShadow, *, day: date) -> str:
    out = [
        f"# Entry-quality shadow (live signals) — {day}",
        "",
        f"_Read-only. The entry-quality overlay over the tradeable signal cohort since "
        f"{r.since.date()} ({r.n_signals} signals). **diversity** is ACTIVE (the ≥2-factor hard "
        "rule — single-factor signals no longer enter); **sl_atr** is SHADOW (measured only). A "
        "flagged set net-negative and worse than passed is the evidence to flip sl_atr active._",
        "",
        "| set | signals | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row("diversity FLAGGED (blocked live)", r.div_flagged),
        _row("diversity passed", r.div_passed),
        _row("sl_atr FLAGGED (shadow)", r.sl_flagged),
        _row("sl_atr passed", r.sl_passed),
        "",
    ]
    ready, reason = sl_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    out += [
        f"**sl_atr flip readiness:** {tag} — {reason}. Flipping sl_atr active also needs explicit "
        "user sign-off (behaviour-changing, reversible via `entry_sl_atr_gate_mode=shadow`).",
        "",
        "_diversity is active by user sign-off (2026-08-18, the SRTL loss) — enforcing the stated "
        "'never a single indicator' rule, so its flagged set no longer trades live._",
        "",
    ]
    return "\n".join(out) + "\n"
