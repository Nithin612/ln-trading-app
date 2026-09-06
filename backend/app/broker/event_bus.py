"""Phase 7.3 / A32 — the order-event bus.

Small on purpose. The external review's clearest Phase-7 finding was that *the bus is the
easy part* — vnpy's is 145 lines — and that the cost lives in the order FSM and
reconciliation. So this does four things and refuses to grow a fifth:

1. **Per-handler exception isolation.** One handler raising must not stop the others, or
   an unrelated reporting bug silently halts order processing.
2. **Snapshot iteration.** A handler that subscribes or unsubscribes mid-dispatch must not
   mutate the list being walked.
3. **A bounded queue with a STATED overflow policy.** Unbounded is not a policy, it is a
   memory leak with good manners.
4. **⭐ A dead bus is LOUD.** This is the one the review called out specifically, and it
   is the reason the class holds state at all: a bus that has stopped delivering must not
   look identical to a quiet market.

⚠ **Not wired into the live path.** 7.3 builds the machinery; the order path still runs
`place_order` → `place_paper_order` directly. Nothing here changes behaviour yet.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.broker.adapter import OrderEvent

log = logging.getLogger(__name__)

Handler = Callable[["OrderEvent"], None]


class OverflowPolicy(Enum):
    """What a full queue does. There is no default — the caller must choose.

    The project's own precedent (`.claude/rules/python.md`): drop-oldest for LTP-class
    data, **never drop candle-closing events**. Order events are firmly the second kind —
    dropping one loses a fill — so `REFUSE` is what the order path uses, and it is loud.
    """

    DROP_OLDEST = "drop_oldest"  # for telemetry-class streams
    REFUSE = "refuse"  # for anything whose loss is a correctness bug


class BusOverflowError(Exception):
    """The queue is full and the policy is REFUSE."""


class BusStoppedError(Exception):
    """Publish attempted on a stopped bus.

    ⭐ **This is the "a dead bus must be loud" rule.** The tempting implementation is to
    ignore publishes after stop — it makes shutdown tidy. It also means a bus that died
    early produces exactly the same observable behaviour as a market with no events: an
    empty log and a calm dashboard. Raising converts a silent data-loss bug into a stack
    trace.
    """


@dataclass
class BusStats:
    published: int = 0
    delivered: int = 0
    handler_errors: int = 0
    dropped: int = 0
    last_publish_at: datetime | None = None
    last_error: str | None = None


@dataclass
class EventBus:
    """A synchronous, in-process fan-out for `OrderEvent`s.

    Synchronous because the order path is already inside a database transaction when
    events are emitted: a handler that persists an event must run in that transaction,
    not after it. Making the bus async would put the durable write outside the
    transaction that justified it — the `flush()` vs `commit()` distinction
    (`.claude/rules/python.md`) applied to fan-out.
    """

    name: str = "orders"
    maxlen: int = 1000
    overflow: OverflowPolicy = OverflowPolicy.REFUSE

    _handlers: list[Handler] = field(default_factory=list, init=False)
    _recent: deque[OrderEvent] = field(init=False)
    _running: bool = field(default=True, init=False)
    stats: BusStats = field(default_factory=BusStats, init=False)

    def __post_init__(self) -> None:
        self._recent = deque(maxlen=self.maxlen)

    # ── subscription ──────────────────────────────────────────────────────────

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        """Register a handler; returns an unsubscribe callable.

        Returning the unsubscriber rather than exposing `unsubscribe(handler)` means a
        caller cannot accidentally remove a *different* handler that happens to compare
        equal — bound methods of two instances of the same class do.
        """
        self._handlers.append(handler)

        def _unsubscribe() -> None:
            try:
                self._handlers.remove(handler)
            except ValueError:  # already gone; idempotent by design
                pass

        return _unsubscribe

    @property
    def handler_count(self) -> int:
        return len(self._handlers)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    # ── publish ───────────────────────────────────────────────────────────────

    def publish(self, event: OrderEvent) -> int:
        """Deliver to every handler. Returns how many handlers ran without raising.

        ⚠ **Never re-raises a handler's exception.** One broken handler must not stop the
        others, and must not roll back the caller's order processing — a reporting bug is
        not a reason to fail a fill. Errors are counted and logged with the handler named,
        so "quietly swallowed" is not the same as "invisible": `stats.handler_errors` is
        the thing an alarm watches.
        """
        if not self._running:
            raise BusStoppedError(
                f"bus {self.name!r} is stopped; refusing to publish "
                f"{event.kind.value} for {event.client_order_id} — "
                "a stopped bus that accepted publishes would look exactly like a "
                "quiet market"
            )

        if self.overflow is OverflowPolicy.REFUSE and len(self._recent) >= self.maxlen:
            self.stats.dropped += 1
            raise BusOverflowError(
                f"bus {self.name!r} at capacity ({self.maxlen}); refusing "
                f"{event.kind.value} for {event.client_order_id}. Order events are not "
                "droppable — drain or raise maxlen."
            )
        # DROP_OLDEST needs no branch: the deque's own maxlen evicts, and we count it.
        if self.overflow is OverflowPolicy.DROP_OLDEST and len(self._recent) >= self.maxlen:
            self.stats.dropped += 1

        self._recent.append(event)
        self.stats.published += 1
        self.stats.last_publish_at = datetime.now(tz=UTC)

        delivered = 0
        # Snapshot: a handler may subscribe or unsubscribe during dispatch, and mutating
        # the list being iterated would skip a handler or raise.
        for handler in list(self._handlers):
            try:
                handler(event)
                delivered += 1
            except Exception as exc:  # noqa: BLE001 — isolation is the whole point
                self.stats.handler_errors += 1
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                log.exception(
                    "event-bus handler %r failed on %s for %s (bus=%s); "
                    "continuing to the remaining %d handler(s)",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.kind.value,
                    event.client_order_id,
                    self.name,
                    len(self._handlers) - 1,
                )
        self.stats.delivered += delivered
        return delivered

    # ── introspection ─────────────────────────────────────────────────────────

    def recent(self, client_order_id: str | None = None) -> list[OrderEvent]:
        """The in-memory tail, optionally for one order. Not durable — `order_events` is.

        ⚠ Bounded by `maxlen`, so this is a debugging window, never a source of truth.
        Projecting from here instead of from the table would silently start losing
        history the moment the bus wrapped.
        """
        if client_order_id is None:
            return list(self._recent)
        return [e for e in self._recent if e.client_order_id == client_order_id]
