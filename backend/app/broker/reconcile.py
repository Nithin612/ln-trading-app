"""Phase 7.4 — restart recovery and broker reconciliation.

Two jobs that are usually conflated and should not be:

**Recovery** rebuilds OUR view from OUR durable record. It is deterministic, needs no
broker, and is just `event_store.load_events → order_fsm.project` over every order that
has not reached a terminal state.

**Reconciliation** compares our view against the BROKER's and reports the difference. It
is the one that can find something genuinely surprising, and the one paper cannot
exercise — see the warning below.

⚠ **THE PAPER GATEWAY CANNOT EXERCISE RECONCILIATION'S MAIN PATH.** Every paper submit
ends terminal inside one transaction, so `PaperBrokerAdapter.fetch_open_orders()` is
always empty and there is never a working order to disagree about. A green reconciliation
run against paper is therefore **not evidence that reconciliation works** — it is evidence
that there was nothing to reconcile. That is exactly why 7.2 shipped a read-only Kite
spike rather than trusting the paper adapter to stand in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.broker import event_store, order_fsm
from app.models.trading import OrderEventRow, Position

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.broker.adapter import BrokerAdapter
    from app.broker.order_fsm import OrderState
    from app.models.user import User

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Recovery — our record, replayed
# ──────────────────────────────────────────────────────────────────────────────


async def recover_order_states(
    db: AsyncSession, *, user_id: int, only_active: bool = True
) -> list[OrderState]:
    """Rebuild order state from the durable event stream.

    This is what a process does on restart: it holds no memory of what was in flight, and
    the event stream is the only thing that does. Because fill quantities in the stream
    are CUMULATIVE rather than deltas, replaying is idempotent — running recovery twice
    cannot double a position, which is the property that makes it safe to run
    unconditionally at startup rather than guarding it with a "have we recovered yet"
    flag that would itself need recovering.

    `only_active` is the default because a terminal order needs nothing done to it. Pass
    `False` for a full audit rebuild.
    """
    ids = list(
        (
            await db.execute(
                select(OrderEventRow.client_order_id)
                .where(OrderEventRow.user_id == user_id)
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    out: list[OrderState] = []
    for cid in ids:
        events = await event_store.load_events(db, cid)
        if not events:  # pragma: no cover — the id came from the same table
            continue
        state = order_fsm.project(events)
        if only_active and not state.active:
            continue
        out.append(state)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Reconciliation — our record vs the broker's
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PositionDrift:
    """One disagreement about a position."""

    symbol: str
    local_qty: int
    broker_qty: int

    @property
    def delta(self) -> int:
        return self.broker_qty - self.local_qty


@dataclass(frozen=True)
class Reconciliation:
    """What agreed, what did not, and what could not be checked.

    ⚠ `unknown_to_us` and `unknown_to_broker` are kept SEPARATE and neither is called an
    "error". They mean opposite things and demand opposite responses: an order the broker
    knows about and we do not is potentially live money we are not tracking (urgent); one
    we know about and the broker does not is usually an order that never landed (also
    serious, but the safe action is the reverse).
    """

    gateway: str
    checked_positions: int
    position_drift: tuple[PositionDrift, ...] = ()
    #: broker order ids with no local stream
    unknown_to_us: tuple[str, ...] = ()
    #: our active orders the broker has never heard of
    unknown_to_broker: tuple[str, ...] = ()
    #: stated limitations of THIS run, so a clean result cannot be over-read
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def clean(self) -> bool:
        return not (self.position_drift or self.unknown_to_us or self.unknown_to_broker)

    def summary(self) -> str:
        if self.clean:
            base = f"✅ reconciliation clean against {self.gateway} " \
                   f"({self.checked_positions} position(s))"
        else:
            base = (
                f"⛔ reconciliation found {len(self.position_drift)} position drift(s), "
                f"{len(self.unknown_to_us)} order(s) unknown to us, "
                f"{len(self.unknown_to_broker)} unknown to the broker "
                f"({self.gateway})"
            )
        if self.caveats:
            base += "\n" + "\n".join(f"  ⚠ {c}" for c in self.caveats)
        return base


async def reconcile(
    db: AsyncSession, user: User, adapter: BrokerAdapter, *, mode: str = "paper"
) -> Reconciliation:
    """Compare our view against the broker's. **Reports; never repairs.**

    Automatic repair is deliberately out of scope. A reconciler that "fixes" a
    disagreement it does not understand can turn a reporting discrepancy into a real
    position — and the disagreements worth having are exactly the ones nobody anticipated.
    A16's durable repair queue is where a human-approved fix belongs.
    """
    caveats: list[str] = []

    broker_positions = await adapter.fetch_positions()
    local_rows = list(
        (
            await db.execute(
                select(Position).where(
                    Position.user_id == user.id,
                    Position.mode == mode,
                    Position.closed_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    local_by_symbol: dict[str, int] = {}
    for p in local_rows:
        key = str(p.stock_id)
        local_by_symbol[key] = local_by_symbol.get(key, 0) + (
            p.quantity if p.side.upper() == "LONG" else -p.quantity
        )
    broker_by_symbol = {bp.symbol: bp.quantity for bp in broker_positions}

    drift = tuple(
        PositionDrift(
            symbol=sym,
            local_qty=local_by_symbol.get(sym, 0),
            broker_qty=broker_by_symbol.get(sym, 0),
        )
        for sym in sorted(set(local_by_symbol) | set(broker_by_symbol))
        if local_by_symbol.get(sym, 0) != broker_by_symbol.get(sym, 0)
    )

    broker_orders = await adapter.fetch_open_orders()
    if not broker_orders:
        caveats.append(
            "the broker reported NO open orders — for the paper gateway that is "
            "structural (every submit ends terminal in one transaction), so the "
            "order-matching half of this run verified nothing"
        )
    ours_active = {s.client_order_id for s in await recover_order_states(db, user_id=user.id)}
    theirs = {o.client_order_id for o in broker_orders if o.client_order_id}

    unknown_to_us = tuple(
        sorted(o.broker_order_id for o in broker_orders if o.client_order_id not in ours_active)
    )
    unknown_to_broker = tuple(sorted(ours_active - theirs)) if broker_orders else ()

    if adapter.gateway == "paper":
        caveats.append(
            "paper `fetch_funds()` is derived from the same rows we would compare it "
            "against, so it is not queried here — a match would be arithmetic, not "
            "corroboration"
        )

    result = Reconciliation(
        gateway=adapter.gateway,
        checked_positions=len(set(local_by_symbol) | set(broker_by_symbol)),
        position_drift=drift,
        unknown_to_us=unknown_to_us,
        unknown_to_broker=unknown_to_broker,
        caveats=tuple(caveats),
    )
    if not result.clean:
        log.error("reconciliation drift: %s", result.summary())
    return result


def local_exposure(positions: list[Position]) -> Decimal:
    """Signed notional of a local book — a cheap sanity figure for the report."""
    total = Decimal(0)
    for p in positions:
        signed = p.quantity if p.side.upper() == "LONG" else -p.quantity
        total += Decimal(signed) * Decimal(str(p.avg_entry_price))
    return total
