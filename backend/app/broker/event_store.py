"""Phase 7.3 — the durable side of the order-event stream.

`app/broker/adapter.py` defines the in-memory `OrderEvent`; this writes it to
`order_events` and reads it back. They are separate on purpose: the adapter must be usable
without a session (7.2's tests drive it with an in-memory sink), and the storage layer must
be usable without an adapter (7.4 replays a stream nobody is currently producing).

**Sequence allocation is the whole design question here.** `seq` must be per-order,
monotonic and gapless, and two writers must never agree on the same number. The answer is
NOT to compute `max(seq) + 1` optimistically and hope: that races, and the race is silent —
two events land, one wins, and the loser's fact is gone. Instead the `UNIQUE(client_order_id,
seq)` constraint is allowed to REFUSE the collision, and `append` surfaces it. A refused
write is a bug to fix; a silently dropped fill is a position you do not know you hold.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.broker.adapter import EventKind, OrderEvent
from app.models.trading import OrderEventRow

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


class DuplicateSequenceError(Exception):
    """Two events claimed the same `(client_order_id, seq)`.

    Surfaced rather than swallowed. It means either a concurrent writer or a replay that
    should have been idempotent at a higher level, and both are conditions where guessing
    produces a confident wrong answer about what an order did.
    """


async def next_seq(db: AsyncSession, client_order_id: str) -> int:
    """The next sequence number for an order.

    ⚠ **Read-then-write, so it is not a lock.** It is correct under the single-writer
    order path we actually have, and the UNIQUE constraint is what catches the day that
    stops being true — which is why `append` translates the integrity error into a named
    exception instead of letting it surface as an opaque database failure.
    """
    current = (
        await db.execute(
            select(func.max(OrderEventRow.seq)).where(
                OrderEventRow.client_order_id == client_order_id
            )
        )
    ).scalar()
    return int(current or 0) + 1


async def append(
    db: AsyncSession,
    *,
    client_order_id: str,
    kind: EventKind,
    user_id: int,
    stock_id: int | None = None,
    signal_id: str | None = None,
    payload: dict[str, object] | None = None,
    at: datetime | None = None,
    seq: int | None = None,
) -> OrderEventRow:
    """Append one event. Flushes (so the row is visible to this session) but does NOT commit.

    The caller owns the transaction, and that is deliberate: the order path emits
    `submitted` and then possibly `denied` inside the same unit of work as the decision
    itself. Committing here would make the event durable while the decision it describes
    could still roll back — the `flush()` vs `commit()` distinction in
    `.claude/rules/python.md`, applied where it matters most.
    """
    row = OrderEventRow(
        client_order_id=client_order_id,
        seq=seq if seq is not None else await next_seq(db, client_order_id),
        kind=kind.value,
        at=at or datetime.now(tz=UTC),
        user_id=user_id,
        stock_id=stock_id,
        signal_id=signal_id,
        payload=dict(payload or {}),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateSequenceError(
            f"{client_order_id} already has seq {row.seq} — concurrent writer, or a "
            "replay that should have been idempotent higher up"
        ) from exc
    return row


async def load_events(db: AsyncSession, client_order_id: str) -> list[OrderEvent]:
    """One order's stream, in `seq` order, as in-memory events.

    Returned as `adapter.OrderEvent` rather than ORM rows so `order_fsm.project` has one
    input type whatever the source — a live bus or this table. 7.4's restart recovery is
    exactly "load_events → project", and it must not care which.

    ⚠ An unknown `kind` string raises rather than being skipped. A row we cannot interpret
    means the projection would be built on a partial stream, and a confidently wrong order
    state is worse than a loud stop.
    """
    rows = (
        (
            await db.execute(
                select(OrderEventRow)
                .where(OrderEventRow.client_order_id == client_order_id)
                .order_by(OrderEventRow.seq)
            )
        )
        .scalars()
        .all()
    )
    out: list[OrderEvent] = []
    for r in rows:
        try:
            kind = EventKind(r.kind)
        except ValueError as exc:
            raise ValueError(
                f"{client_order_id} seq {r.seq} has unknown kind {r.kind!r} — refusing to "
                "project a partial stream"
            ) from exc
        out.append(
            OrderEvent(
                client_order_id=r.client_order_id,
                seq=r.seq,
                kind=kind,
                at=r.at,
                payload=dict(r.payload or {}),
            )
        )
    return out


async def refusals_between(
    db: AsyncSession,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
) -> list[OrderEventRow]:
    """Every refusal in a window — **the query this whole table exists to make possible.**

    Before the event stream, this could not be answered at all: a refused order raised an
    exception and wrote nothing, so the record of what the risk layer turned away lived
    only in a log line. Returns both kinds; the caller reads `kind` to separate *ours*
    (`denied`) from *the broker's* (`rejected`), which is the distinction that says whether
    our thresholds or the market moved.
    """
    return list(
        (
            await db.execute(
                select(OrderEventRow)
                .where(
                    OrderEventRow.user_id == user_id,
                    OrderEventRow.kind.in_(
                        (EventKind.DENIED.value, EventKind.REJECTED.value)
                    ),
                    OrderEventRow.at >= start,
                    OrderEventRow.at < end,
                )
                .order_by(OrderEventRow.at)
            )
        )
        .scalars()
        .all()
    )


# ── Why there is no `EventSink` that writes to the DB ────────────────────────────
#
# An `EventSink` is `Callable[[OrderEvent], None]` — SYNCHRONOUS — and persisting needs an
# await. Papering over that with `asyncio.create_task` would produce an orphan task writing
# OUTSIDE the caller's transaction, which is precisely the ownership rule this module exists
# to respect (and `.claude/rules/python.md` forbids orphan tasks besides).
#
# So the live path awaits `append()` directly rather than routing persistence through the
# bus, and the bus stays what it is: in-process fan-out for handlers that need no session.
# Written down because "why is there no DB sink?" is otherwise a reasonable question that
# gets answered by someone writing the wrong thing.
