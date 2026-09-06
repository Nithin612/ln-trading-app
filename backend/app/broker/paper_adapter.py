"""Phase 7.2 — `PaperBrokerAdapter`: the paper broker behind the port.

The interesting thing this class does is **give up its own synchrony**. Paper fills
inside one transaction and could return the fill directly; instead `submit()` returns an
`Ack` and the fill arrives as a `FILLED` event on the same channel a real broker would
use. Callers written against this cannot quietly assume a fill is available on return,
which is the whole reason the port exists.

⚠ **Not wired into the live order path.** `place_order` still calls `place_paper_order`
directly; this adapter wraps the same function without replacing that call. 7.3 moves
the path onto the event stream. Until then nothing about a real order changes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.broker.adapter import (
    GATEWAY_PAPER,
    Ack,
    AckStatus,
    BrokerOrder,
    BrokerPosition,
    ErrorClass,
    EventKind,
    EventSink,
    Funds,
    OrderEvent,
    OrderRequest,
    namespaced_id,
)
from app.broker.paper_broker import PaperOrderError, place_paper_order
from app.models.signal import Signal
from app.models.trading import Position

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

log = logging.getLogger(__name__)


class PaperBrokerAdapter:
    """`BrokerAdapter` over the existing paper broker.

    Holds `db` and `user` because the paper broker is not a remote service — it is a
    function over our own session. A Kite adapter will hold a `ThrottledKite` in the
    same slot. That asymmetry is contained here, which is the point of a port.
    """

    gateway = GATEWAY_PAPER

    def __init__(self, db: AsyncSession, user: User, sink: EventSink) -> None:
        self._db = db
        self._user = user
        self._sink = sink
        #: per-order monotonic sequence. 7.3 replaces this with the durable column;
        #: keeping it here now means the ordering contract is already exercised.
        self._seq: dict[str, int] = {}

    # ── event plumbing ────────────────────────────────────────────────────────

    def _emit(self, client_order_id: str, kind: EventKind, **payload: object) -> OrderEvent:
        seq = self._seq.get(client_order_id, 0) + 1
        self._seq[client_order_id] = seq
        event = OrderEvent(
            client_order_id=client_order_id,
            seq=seq,
            kind=kind,
            at=datetime.now(tz=UTC),
            payload=dict(payload),
        )
        self._sink(event)
        return event

    # ── the port ──────────────────────────────────────────────────────────────

    async def submit(self, req: OrderRequest) -> Ack:
        """Fill via the paper broker, but answer with an Ack and emit the fill.

        A `PaperOrderError` is the paper analogue of a broker rejection — the request
        landed and was refused on its merits (through-stop, off-market, zero size,
        notional cap). It is TERMINAL, never retried: re-sending an order the broker
        already refused for a stated reason just refuses again.
        """
        now = datetime.now(tz=UTC)
        signal = await self._db.get(Signal, req.signal_id) if req.signal_id else None
        if signal is None:
            self._emit(
                req.client_order_id,
                EventKind.REJECTED,
                reason="signal not found",
                error_class=ErrorClass.TERMINAL.value,
            )
            return Ack(
                client_order_id=req.client_order_id,
                status=AckStatus.REJECTED,
                reason="signal not found",
                at=now,
            )

        try:
            order, _position = await place_paper_order(
                self._db, self._user, signal, side=req.side, quantity=req.quantity
            )
        except (PaperOrderError, ValueError) as exc:
            # The broker answered — with "no". That is an Ack, not an exception the
            # caller has to catch, which is the difference the FSM needs in 7.3.
            self._emit(
                req.client_order_id,
                EventKind.REJECTED,
                reason=str(exc),
                error_class=ErrorClass.TERMINAL.value,
            )
            return Ack(
                client_order_id=req.client_order_id,
                status=AckStatus.REJECTED,
                reason=str(exc),
                at=now,
            )

        broker_order_id = namespaced_id(self.gateway, str(order.id))
        self._emit(
            req.client_order_id,
            EventKind.ACCEPTED,
            broker_order_id=broker_order_id,
        )
        # Paper fills immediately — but it is still an EVENT, on the same channel Kite
        # will use, rather than a return value.
        self._emit(
            req.client_order_id,
            EventKind.FILLED,
            broker_order_id=broker_order_id,
            filled_qty=order.filled_qty,
            filled_price=str(order.filled_price) if order.filled_price is not None else None,
        )
        return Ack(
            client_order_id=req.client_order_id,
            status=AckStatus.ACCEPTED,
            broker_order_id=broker_order_id,
            at=now,
        )

    async def cancel(self, client_order_id: str) -> Ack:
        """Nothing to cancel: a paper order is terminal the moment `submit` returns.

        Answered honestly as a REJECTED ack rather than a cheerful no-op, because a
        caller that believes it cancelled something is worse off than one told it could
        not. When 7.3 introduces genuinely pending paper orders this gains a real body.
        """
        return Ack(
            client_order_id=client_order_id,
            status=AckStatus.REJECTED,
            reason="paper orders reach a terminal state synchronously; nothing to cancel",
            at=datetime.now(tz=UTC),
        )

    async def fetch_open_orders(self) -> list[BrokerOrder]:
        """Always empty, and that is the truthful answer for this gateway.

        Paper has no working orders — every submit ends filled or rejected. 7.4 must
        therefore NOT read "no open orders" as evidence that reconciliation works; the
        paper gateway cannot exercise that path, which is exactly why the Kite spike in
        this slice is read-only rather than skipped.
        """
        return []

    async def fetch_positions(self) -> list[BrokerPosition]:
        """Our own open paper positions, in the broker-shaped vocabulary.

        Signed quantity: negative is short, matching how a broker reports a net
        position, rather than our LONG/SHORT string.
        """
        rows = (
            await self._db.execute(
                select(Position).where(
                    Position.user_id == self._user.id,
                    Position.mode == "paper",
                    Position.closed_at.is_(None),
                )
            )
        ).scalars().all()
        out: list[BrokerPosition] = []
        for p in rows:
            qty = p.quantity if p.side.upper() == "LONG" else -p.quantity
            out.append(
                BrokerPosition(
                    symbol=str(p.stock_id),
                    quantity=qty,
                    average_price=Decimal(str(p.avg_entry_price)),
                )
            )
        return out

    async def fetch_funds(self) -> Funds:
        """Paper's declared capital, with `used` derived from open positions.

        ⚠ This is NOT an independent source. For paper it is computed from the same
        rows A42 derives from, so agreement proves nothing — the cross-check only
        becomes meaningful against a real broker. Stated here so a green reconciliation
        against the paper gateway is not mistaken for evidence.
        """
        positions = await self.fetch_positions()
        used = sum(
            (abs(p.quantity) * p.average_price for p in positions), Decimal(0)
        )
        return Funds(available=self._user.capital_inr - used, used=used)
