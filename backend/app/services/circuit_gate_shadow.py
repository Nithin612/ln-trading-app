"""Circuit-gate shadow measurement (Phase 6.8.3) — "measure before gating".

The circuit overlay (`app/signals/circuit_guard.py`) runs shadow-first: every
paper entry is judged against its cached circuit band and the verdict is stamped
on the order (`broker_payload["circuit_gate"]`), but nothing is suppressed until
the gate is flipped active. This module aggregates those stamped verdicts into
the forward evidence for that flip — the live counterpart to the regime gate's
`regime_gate_shadow`, and read-only like it.

The evidence that matters: of the entries the gate WOULD block (entered within
`circuit_proximity_pct` of the adverse band), were they net-losing? A blocked set
that made money live would mean the band-proximity heuristic is suppressing good
trades — do NOT flip. Outcome is the realized P&L of the position each blocked
entry opened (linked by signal_id), for the closed ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.trading import Order, Position
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals.eligibility import mode_banner

# Forward-evidence bar for flipping the circuit gate active — the project's n=20
# rank floor (same as the regime gate): enough resolved blocked trades to trust
# the sign, not a re-powering. Advice for the human sign-off, never an auto-flip.
FORWARD_EVIDENCE_TARGET_N = 20


@dataclass(frozen=True)
class BlockedEntry:
    symbol: str
    side: str
    adverse: str | None
    distance_pct: Decimal | None
    realized_pnl: Decimal | None  # None while the position is still open


@dataclass(frozen=True)
class CircuitGateShadow:
    """What the circuit overlay would do to the live paper-entry cohort."""

    since: datetime
    n_evaluated: int  # entries carrying a circuit verdict
    n_with_band: int  # the gate had a cached band (real evaluation)
    n_no_band: int  # fail-open — no band cached at entry time
    n_blocked: int  # would-suppress (within proximity of the adverse band)
    blocked_resolved: int  # blocked entries whose position has closed
    blocked_realized_total: Decimal | None  # Σ realized P&L of those closed ones
    blocked: list[BlockedEntry] = field(default_factory=list)


async def compute_circuit_gate_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> CircuitGateShadow:
    """Aggregate the circuit verdicts stamped on paper entry orders since `since`."""
    orders = (
        await db.execute(
            select(Order).where(Order.mode == "paper", Order.placed_at >= since)
        )
    ).scalars().all()
    # Opening orders carry a dict "circuit_gate" stamp; closing orders never do.
    # Bind the narrowed verdict dict alongside its order so the type is carried.
    stamped: list[tuple[Order, dict[str, Any]]] = []
    for o in orders:
        payload = o.broker_payload
        if isinstance(payload, dict):
            cg = payload.get("circuit_gate")
            if isinstance(cg, dict):
                stamped.append((o, cg))

    n_with_band = n_no_band = n_blocked = 0
    blocked_orders: list[tuple[Order, dict[str, Any]]] = []
    for o, v in stamped:
        if v.get("has_band"):
            n_with_band += 1
        else:
            n_no_band += 1
        if v.get("blocked"):
            n_blocked += 1
            blocked_orders.append((o, v))

    blocked, resolved, total = await _link_blocked_outcomes(db, blocked_orders)

    return CircuitGateShadow(
        since=since,
        n_evaluated=len(stamped),
        n_with_band=n_with_band,
        n_no_band=n_no_band,
        n_blocked=n_blocked,
        blocked_resolved=resolved,
        blocked_realized_total=(total if resolved else None),
        blocked=blocked,
    )


async def _link_blocked_outcomes(
    db: AsyncSession, blocked_orders: list[tuple[Order, dict[str, Any]]]
) -> tuple[list[BlockedEntry], int, Decimal]:
    """Resolve each blocked entry's symbol and the realized P&L of the TRADE it
    opened, batched — one query for outcomes, one for symbols.

    Deduped BY SIGNAL: repeat/average-in entries share a signal_id and map to ONE
    trade, so counting per order would double-count the outcome (bug-hunter MED,
    2026-08-17). We count each distinct blocked signal once, and a signal's
    realized P&L is the SUM of all its closed positions (reopen-safe). The table
    shows one row per blocked signal so it never implies N losses from one trade."""
    # First blocked order per signal carries the display fields (symbol/side/dist).
    first_by_sig: dict[str, tuple[Order, dict[str, Any]]] = {}
    no_signal: list[tuple[Order, dict[str, Any]]] = []
    for o, v in blocked_orders:
        if o.signal_id is None:
            no_signal.append((o, v))
        elif o.signal_id not in first_by_sig:
            first_by_sig[o.signal_id] = (o, v)

    stock_ids = {o.stock_id for o, _ in blocked_orders}
    realized_by_sig, sym_by_stock = await _load_outcomes_and_symbols(
        db, list(first_by_sig), stock_ids
    )

    def _row(o: Order, v: dict[str, Any], realized: Decimal | None) -> BlockedEntry:
        dist = v.get("distance_pct")
        return BlockedEntry(
            symbol=sym_by_stock.get(o.stock_id, str(o.stock_id)),
            side=str(v.get("side", "?")),
            adverse=v.get("adverse"),
            distance_pct=Decimal(str(dist)) if dist is not None else None,
            realized_pnl=realized,
        )

    blocked: list[BlockedEntry] = []
    resolved = 0
    total = Decimal("0")
    for sig_id, (o, v) in first_by_sig.items():
        realized = realized_by_sig.get(sig_id)
        if realized is not None:
            resolved += 1
            total += realized
        blocked.append(_row(o, v, realized))
    # Signal-less blocked entries can't be outcome-linked; still surface them.
    blocked.extend(_row(o, v, None) for o, v in no_signal)
    return blocked, resolved, total


async def _load_outcomes_and_symbols(
    db: AsyncSession, sig_ids: list[str], stock_ids: set[int]
) -> tuple[dict[str, Decimal], dict[int, str]]:
    """Batched lookups for `_link_blocked_outcomes`: realized P&L per signal (Σ of
    all its CLOSED positions, reopen-safe) and symbol per stock — one query each."""
    realized_by_sig: dict[str, Decimal] = {}
    if sig_ids:
        for sig_id, realized, closed_at in (
            await db.execute(
                select(Position.signal_id, Position.realized_pnl, Position.closed_at).where(
                    Position.signal_id.in_(sig_ids)
                )
            )
        ).all():
            if closed_at is not None:
                realized_by_sig[sig_id] = realized_by_sig.get(sig_id, Decimal("0")) + realized
    sym_by_stock: dict[int, str] = {}
    if stock_ids:
        for sid, sym in (
            await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids)))
        ).all():
            sym_by_stock[sid] = sym
    return realized_by_sig, sym_by_stock


def forward_evidence_ready(r: CircuitGateShadow) -> tuple[bool, str]:
    """Is there enough LIVE forward evidence to justify flipping the gate active?
    Bar (both): ≥ FORWARD_EVIDENCE_TARGET_N resolved blocked trades AND that
    blocked set net-losing (blocking them would have helped). Never flips
    anything — advice for the human sign-off, which is a separate required step."""
    n = r.blocked_resolved
    if n < FORWARD_EVIDENCE_TARGET_N:
        return False, f"{n}/{FORWARD_EVIDENCE_TARGET_N} resolved blocked trades — keep accruing"
    total = r.blocked_realized_total
    if total is None or total >= 0:
        got = "—" if total is None else f"₹{total:,.0f}"
        return False, (
            f"{n} resolved blocked trades but the blocked set is net-POSITIVE ({got}) — "
            "the proximity heuristic is suppressing good trades; do NOT flip"
        )
    return True, (
        f"{n} resolved blocked trades, net-losing (₹{total:,.0f}) — blocking them would have "
        "helped; READY for sign-off + flip"
    )


def readiness_line(r: CircuitGateShadow) -> str:
    """One-line status for the daily run's stdout (the passive reminder)."""
    ready, reason = forward_evidence_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[circuit-gate forward evidence] {tag} — {reason}"


MODE_EFFECTIVE_FROM = date(2026, 8, 17)
"""When `circuit_gate_mode` last changed (built shadow-first in 6.8.3, never flipped).

Printed beside the mode so this report cannot describe a differently-moded earlier
window in the present tense — the generalisation of the regime-gate fix
(quant-verifier, 2026-09-02). **Bump on every mode flip.**
"""


def render_markdown(r: CircuitGateShadow, *, day: date, mode: str) -> str:
    """`mode` is the LIVE `circuit_gate_mode` - see `eligibility.mode_banner` for why a
    shadow report must never hardcode "SHADOW" in its own preamble."""
    out = [
        f"# Circuit-gate shadow (live paper entries) — {day}",
        "",
        "_Read-only. What the circuit overlay WOULD suppress on the live paper-entry "
        f"cohort since {r.since.date()}: entries within the proximity threshold of the "
        f"ADVERSE circuit band (long→lower, short→upper). "
        f"{mode_banner(mode, since=MODE_EFFECTIVE_FROM.isoformat())} "
        "A net-POSITIVE blocked set means the heuristic is killing good trades — do not "
        "flip to active._",
        "",
        f"- entries evaluated: **{r.n_evaluated}** "
        f"(with a live band: {r.n_with_band}; no band / fail-open: {r.n_no_band})",
        f"- would-block entries: **{r.n_blocked}** across **{len(r.blocked)}** blocked "
        f"signal(s) · resolved trades: {r.blocked_resolved}",
        (
            f"- blocked set realized P&L: **₹{r.blocked_realized_total:,.2f}**"
            if r.blocked_realized_total is not None
            else "- blocked set realized P&L: — (none resolved yet)"
        ),
        "",
    ]
    if r.blocked:
        out += [
            "| symbol | side | adverse band | distance | realized P&L |",
            "|---|---|---|--:|--:|",
        ]
        for b in r.blocked:
            dist = f"{b.distance_pct}%" if b.distance_pct is not None else "—"
            pnl = f"₹{b.realized_pnl:,.2f}" if b.realized_pnl is not None else "open"
            out.append(f"| {b.symbol} | {b.side} | {b.adverse or '—'} | {dist} | {pnl} |")
        out.append("")
    ready, reason = forward_evidence_ready(r)
    out += [
        f"**Flip readiness:** {'✅ READY' if ready else '⏳ NOT READY'} — {reason}. "
        "Flipping to active also requires explicit user sign-off (behaviour-changing, "
        "reversible via `circuit_gate_mode=shadow`).",
        "",
    ]
    return "\n".join(out) + "\n"
