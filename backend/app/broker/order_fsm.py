"""Phase 7.3 — the order state machine, and the projection built from it.

`orders` is a projection of `order_events`; this module is the rule that governs which
event may follow which, and how a stream folds into a current state.

**The distinction the whole FSM exists for** (the Nautilus one, settled in 7.0):

    DENIED   — WE refused it. Entirely within our control, so a rising denial rate is a
               finding about our own thresholds.
    REJECTED — THE BROKER refused it. A finding about the market or our credentials.

Collapsing those into one "failed" bucket destroys the only signal separating *"our rules
are too tight"* from *"the exchange said no"* — which is exactly the question a 45-day
cycle-2 rehearsal is there to answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.broker.adapter import ACTIVE_KINDS, TERMINAL_KINDS, EventKind

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from app.broker.adapter import OrderEvent


class IllegalTransitionError(Exception):
    """An event that cannot follow the current state.

    Raised rather than logged: an impossible transition means either the broker sent
    something we do not understand or our own emitter is wrong, and both are conditions
    where continuing to project would produce a confident, incorrect state. A dead
    reckoning is worse than a stop.
    """


#: The legal successors of each state. `None` is "no events yet".
#:
#: Read the two interesting rows:
#:
#: * **SUBMITTED → DENIED | REJECTED | ACCEPTED.** Both refusals are reachable from the
#:   same place, which is why they have to be distinct *kinds* rather than one kind with
#:   a flag — the projection cannot recover the distinction after the fact.
#: * **CANCEL_REQUESTED → FILLED.** A cancel that loses the race to a fill is not an
#:   error, it is Tuesday. Modelling it as illegal would make the FSM raise on a routine
#:   market outcome, and the natural "fix" for that is to stop raising at all.
_TRANSITIONS: dict[EventKind | None, frozenset[EventKind]] = {
    None: frozenset({EventKind.SUBMITTED}),
    EventKind.SUBMITTED: frozenset(
        {EventKind.DENIED, EventKind.ACCEPTED, EventKind.REJECTED}
    ),
    EventKind.ACCEPTED: frozenset(
        {
            EventKind.PARTIALLY_FILLED,
            EventKind.FILLED,
            EventKind.CANCEL_REQUESTED,
            EventKind.REJECTED,
            EventKind.EXPIRED,
        }
    ),
    EventKind.PARTIALLY_FILLED: frozenset(
        {
            EventKind.PARTIALLY_FILLED,
            EventKind.FILLED,
            EventKind.CANCEL_REQUESTED,
            EventKind.CANCELLED,
            EventKind.EXPIRED,
        }
    ),
    EventKind.CANCEL_REQUESTED: frozenset(
        {
            EventKind.CANCELLED,
            EventKind.FILLED,  # the cancel lost the race
            EventKind.PARTIALLY_FILLED,
            EventKind.EXPIRED,
        }
    ),
    # Terminal states accept nothing.
    EventKind.DENIED: frozenset(),
    EventKind.REJECTED: frozenset(),
    EventKind.FILLED: frozenset(),
    EventKind.CANCELLED: frozenset(),
    EventKind.EXPIRED: frozenset(),
}


def can_follow(current: EventKind | None, nxt: EventKind) -> bool:
    """Is `nxt` a legal successor of `current`?"""
    return nxt in _TRANSITIONS.get(current, frozenset())


def assert_can_follow(current: EventKind | None, nxt: EventKind) -> None:
    if not can_follow(current, nxt):
        raise IllegalTransitionError(
            f"{nxt.value} cannot follow {current.value if current else '(no events)'}"
        )


@dataclass(frozen=True)
class OrderState:
    """The projection: what the event stream says about one order right now."""

    client_order_id: str
    kind: EventKind | None
    seq: int
    filled_qty: int = 0
    avg_fill_price: Decimal | None = None
    broker_order_id: str | None = None
    reason: str | None = None
    rule: str | None = None
    at: datetime | None = None
    #: kinds seen, in order — cheap provenance for the audit trail
    history: tuple[EventKind, ...] = field(default_factory=tuple)

    @property
    def active(self) -> bool:
        """Can this order still consume capital? (A42's input.)"""
        return self.kind is not None and self.kind in ACTIVE_KINDS

    @property
    def terminal(self) -> bool:
        return self.kind is not None and self.kind in TERMINAL_KINDS

    @property
    def refused(self) -> bool:
        """Refused by anyone — ours or the broker's. Use `kind` for WHICH."""
        return self.kind in (EventKind.DENIED, EventKind.REJECTED)


def project(events: Iterable[OrderEvent], *, strict: bool = True) -> OrderState:
    """Fold an order's events into its current state.

    ⚠ **The stream must be complete and in `seq` order.** A gap means the projection is
    a guess, so `strict` raises on one rather than returning a state that looks fine.
    The `UNIQUE(client_order_id, seq)` constraint is what makes a gap the *only* way this
    can go wrong — duplicates are impossible at the storage layer.

    `strict=False` exists for forensic reading of a stream already known to be damaged;
    it is never the live path.
    """
    ordered = sorted(events, key=lambda e: e.seq)
    if not ordered:
        raise ValueError("cannot project an empty event stream")

    client_order_id = ordered[0].client_order_id
    kind: EventKind | None = None
    filled_qty = 0
    avg_price: Decimal | None = None
    broker_order_id: str | None = None
    reason: str | None = None
    rule: str | None = None
    at: datetime | None = None
    history: list[EventKind] = []
    expected = 1

    for ev in ordered:
        if ev.client_order_id != client_order_id:
            raise ValueError(
                f"mixed streams: {ev.client_order_id!r} in {client_order_id!r}'s projection"
            )
        if strict and ev.seq != expected:
            raise IllegalTransitionError(
                f"{client_order_id}: sequence gap — expected {expected}, got {ev.seq}"
            )
        expected = ev.seq + 1
        if strict:
            assert_can_follow(kind, ev.kind)

        kind = ev.kind
        history.append(ev.kind)
        at = ev.at
        broker_order_id = ev.payload.get("broker_order_id") or broker_order_id
        if ev.kind in (EventKind.DENIED, EventKind.REJECTED):
            reason = ev.payload.get("reason") or reason
            rule = ev.payload.get("rule") or rule
        if ev.kind in (EventKind.PARTIALLY_FILLED, EventKind.FILLED):
            # A fill event reports the CUMULATIVE filled quantity, not a delta. Deltas
            # would make a replayed-but-duplicated event silently double the position;
            # cumulative is idempotent under replay, which matters because replay is how
            # this projection is rebuilt after a restart (7.4).
            qty = ev.payload.get("filled_qty")
            if qty is not None:
                filled_qty = int(qty)
            price = ev.payload.get("filled_price")
            if price is not None:
                avg_price = Decimal(str(price))

    return OrderState(
        client_order_id=client_order_id,
        kind=kind,
        seq=ordered[-1].seq,
        filled_qty=filled_qty,
        avg_fill_price=avg_price,
        broker_order_id=broker_order_id,
        reason=reason,
        rule=rule,
        at=at,
        history=tuple(history),
    )
