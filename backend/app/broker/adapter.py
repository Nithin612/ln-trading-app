"""Phase 7.2 — the BrokerAdapter port, and the order-event vocabulary it speaks.

Designed in 7.0 (`docs/phases/phase-07.0-oms-design.md`). The one rule everything else
follows from:

    ⭐ submit() returns an Ack, NEVER a Fill.

Paper *can* fill synchronously — it does today, inside `place_paper_order`'s transaction —
and it will still return an `Ack` and then emit `FILLED` on the same event channel a real
broker uses. If paper were allowed to return a fill, every caller would be written against
a synchronous world, and the abstraction would be discovered to be wrong on day 1 of live.
That is precisely the failure the two-cycle plan exists to prevent, so the asynchrony is
imposed on the *paper* side rather than papered over on the Kite side.

**Nothing here is wired into the live order path.** 7.2 defines the port and a paper
implementation; 7.3 persists the event stream and adds the FSM; 7.4 reconciles. The
existing `place_order` → `place_paper_order` path is untouched, so no behaviour and no
recorded number changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# ──────────────────────────────────────────────────────────────────────────────
# Gateways and ids
# ──────────────────────────────────────────────────────────────────────────────

GATEWAY_PAPER = "paper"
GATEWAY_KITE = "kite"


def namespaced_id(gateway: str, raw: str) -> str:
    """`paper:<uuid>` / `kite:<broker_order_id>`.

    Two reasons, and the second is the load-bearing one:

    1. A broker id can never collide with one of ours.
    2. **Reconciliation can distinguish "an order we do not know about" from "an order
       belonging to a different gateway".** Without the namespace those look identical,
       and the correct response to each is the opposite — one is an alarm, the other is
       noise.
    """
    if not gateway or ":" in gateway:
        raise ValueError(f"gateway must be a non-empty bare token, got {gateway!r}")
    if not raw:
        raise ValueError("raw id must be non-empty")
    return f"{gateway}:{raw}"


def split_id(order_id: str) -> tuple[str, str]:
    """Inverse of `namespaced_id`. Raises on an un-namespaced id rather than guessing.

    Guessing a gateway is how a reconciliation loop ends up acting on someone else's
    order, so an unparseable id is a programming error, not a default.
    """
    gateway, sep, raw = order_id.partition(":")
    if not sep or not gateway or not raw:
        raise ValueError(f"order id is not gateway-namespaced: {order_id!r}")
    return gateway, raw


# ──────────────────────────────────────────────────────────────────────────────
# The event vocabulary (A33)
# ──────────────────────────────────────────────────────────────────────────────


class EventKind(Enum):
    """Every state an order can reach. Declared ONCE — the T7 lesson.

    ⭐ `DENIED` and `REJECTED` are separate on purpose. *Denied* is our own risk layer
    and is entirely within our control, so a rising denial rate is a finding about our
    thresholds. *Rejected* is the broker's and is a finding about the market or our
    credentials. Collapsing them into one "failed" bucket destroys the only signal that
    separates "our rules are too tight" from "the exchange said no" — which is exactly
    the question a 45-day cycle-2 rehearsal exists to answer.
    """

    SUBMITTED = "submitted"
    DENIED = "denied"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


#: An order is ACTIVE iff it can still consume capital. That is the whole rule, and it
#: is what makes A42's available-cash derivation correct: `PARTIALLY_FILLED` is active
#: because the remainder can still fill; `DENIED` is terminal because it never can.
ACTIVE_KINDS: frozenset[EventKind] = frozenset(
    {
        EventKind.SUBMITTED,
        EventKind.ACCEPTED,
        EventKind.PARTIALLY_FILLED,
        EventKind.CANCEL_REQUESTED,
    }
)

TERMINAL_KINDS: frozenset[EventKind] = frozenset(
    {
        EventKind.DENIED,
        EventKind.REJECTED,
        EventKind.FILLED,
        EventKind.CANCELLED,
        EventKind.EXPIRED,
    }
)


def is_active(kind: EventKind) -> bool:
    """THE predicate. One function, one place.

    Nothing may re-derive this inline. The precedent is T7, where the gate-mode
    `Literal` was declared nine times and tied together nowhere, so a fourth value would
    have fallen through as "off" on the order path. An exhaustiveness test pins that
    every `EventKind` is classified exactly once.
    """
    return kind in ACTIVE_KINDS


@dataclass(frozen=True)
class OrderEvent:
    """One append-only fact about an order.

    `seq` is per-order and monotonic, so replay is deterministic and a GAP IS
    DETECTABLE — which is the property that makes the projection trustworthy enough to
    reconcile against.
    """

    client_order_id: str
    seq: int
    kind: EventKind
    at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


#: Where an adapter puts events. 7.2 keeps this an in-memory callable; 7.3 replaces the
#: implementation with the durable `order_events` writer. The adapters do not change.
EventSink = Callable[[OrderEvent], None]


# ──────────────────────────────────────────────────────────────────────────────
# Requests and acknowledgements
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OrderRequest:
    """What we ask a broker to do.

    ⚠ Deliberately carries NO Kite-specific fields (`variety`, `validity`, Kite's own
    `product` codes). Those belong in `KiteBrokerAdapter`'s translation layer — put them
    here and the "port" is just Kite's API with an extra indirection, which is the
    standard way a port stops being one.
    """

    client_order_id: str  # ours, gateway-namespaced
    stock_id: int
    symbol: str
    side: str  # BUY | SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET | LIMIT
    limit_price: Decimal | None = None
    #: delivery vs intraday, in OUR vocabulary — the adapter maps it.
    product: str = "DELIVERY"
    signal_id: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {self.side!r}")
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("a LIMIT order needs a limit_price")


class AckStatus(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Ack:
    """The broker's *acknowledgement*. Explicitly not a fill.

    A rejection at submit time is still an Ack — the broker answered. What it is not is
    a statement about whether the order will fill.
    """

    client_order_id: str
    status: AckStatus
    broker_order_id: str | None = None
    reason: str | None = None
    at: datetime | None = None

    @property
    def accepted(self) -> bool:
        return self.status is AckStatus.ACCEPTED


@dataclass(frozen=True)
class BrokerOrder:
    """An order as the BROKER currently sees it — reconciliation input (7.4)."""

    broker_order_id: str
    client_order_id: str | None
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    status: str  # the broker's own word, deliberately un-normalised
    average_price: Decimal | None = None


@dataclass(frozen=True)
class BrokerPosition:
    """A position as the BROKER currently sees it — reconciliation input (7.4)."""

    symbol: str
    quantity: int  # signed: negative is short
    average_price: Decimal


@dataclass(frozen=True)
class Funds:
    """Cash as the BROKER reports it — A42's ground truth to reconcile against.

    We DERIVE available cash locally from the active-order set; this is what we check
    that derivation against. Two independent numbers that must agree is the point — a
    single stored balance would have nothing to disagree with.
    """

    available: Decimal
    used: Decimal


# ──────────────────────────────────────────────────────────────────────────────
# Error classification (A28, pulled to the boundary)
# ──────────────────────────────────────────────────────────────────────────────


class ErrorClass(Enum):
    """⚠ `UNKNOWN` IS NOT RETRYABLE.

    Retrying an order whose fate you do not know is how you end up with two positions.
    The classification lives at the adapter boundary because that is the last place the
    broker's own vocabulary still exists — one layer up it has been flattened into a
    generic exception and the distinction is unrecoverable.
    """

    RETRYABLE = "retryable"  # network, 5xx, rate limit — the request did not land
    TERMINAL = "terminal"  # rejected, insufficient funds, bad symbol — it landed and failed
    UNKNOWN = "unknown"  # we cannot tell. Do NOT retry.


class BrokerAdapterError(Exception):
    """An adapter-level failure carrying its classification."""

    def __init__(self, message: str, error_class: ErrorClass) -> None:
        super().__init__(message)
        self.error_class = error_class

    @property
    def retryable(self) -> bool:
        return self.error_class is ErrorClass.RETRYABLE


# ──────────────────────────────────────────────────────────────────────────────
# The port
# ──────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class BrokerAdapter(Protocol):
    """The interface a `KiteBrokerAdapter` will implement, with paper behind it today.

    ⚠ There is deliberately **no `place_and_wait()`**. A convenience that
    re-synchronises the world would get used, and the asynchrony would leak straight
    back out through it.

    ⚠ There is deliberately **no GTT**. Only reality validates GTT semantics, so it is
    post-cycle-2 work.
    """

    gateway: str

    async def submit(self, req: OrderRequest) -> Ack:
        """Send an order. Returns an acknowledgement; fills arrive as events."""
        ...

    async def cancel(self, client_order_id: str) -> Ack:
        """Request cancellation. Confirmation arrives as a `CANCELLED` event."""
        ...

    async def fetch_open_orders(self) -> list[BrokerOrder]:
        """What the broker thinks is still working (7.4 reconciliation)."""
        ...

    async def fetch_positions(self) -> list[BrokerPosition]:
        """What the broker thinks we hold (7.4 reconciliation)."""
        ...

    async def fetch_funds(self) -> Funds:
        """What the broker thinks our cash is (A42's cross-check)."""
        ...
