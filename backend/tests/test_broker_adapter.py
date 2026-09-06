"""Phase 7.2 — the BrokerAdapter port and its paper implementation.

The load-bearing assertions here are structural rather than behavioural:

- `submit()` returns an `Ack` and NEVER a fill, even for paper, which fills
  synchronously and could trivially have returned one;
- every `EventKind` is classified active-or-terminal exactly once, so `is_active()`
  cannot silently mis-file a state the way T7's nine gate-mode declarations could;
- a refusal is an `Ack`, not an exception, which is the distinction 7.3's FSM needs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.broker import adapter as ad
from app.broker.paper_adapter import PaperBrokerAdapter
from app.models.signal import Signal
from app.models.trading import Position
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

# ── fixtures ──────────────────────────────────────────────────────────────────


async def _make_user(db: AsyncSession, *, capital: Decimal = Decimal("100000")) -> User:
    from app.core.security import hash_password

    user = User(
        email="adapter@example.com",
        password_hash=hash_password("pass123"),
        full_name="Adapter Tester",
        capital_inr=capital,
        risk_per_trade_pct=Decimal("2.0"),
        daily_loss_limit_pct=Decimal("3.00"),
        max_trades_per_day=10,
        allow_offmarket_entry=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_signal(
    db: AsyncSession, stock_id: int, *, entry: str = "500.0000", sl: str = "480.0000"
) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit="540.0000", suggested_qty=100,
        confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },
        headline="BUY ADAPTER", status="active",
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


def _collector() -> tuple[list[ad.OrderEvent], ad.EventSink]:
    events: list[ad.OrderEvent] = []
    return events, events.append


# ── 1. ids and namespacing ────────────────────────────────────────────────────


class TestNamespacedIds:
    def test_round_trip(self) -> None:
        oid = ad.namespaced_id("kite", "250906000123456")
        assert oid == "kite:250906000123456"
        assert ad.split_id(oid) == ("kite", "250906000123456")

    def test_rejects_un_namespaced_id(self) -> None:
        """Guessing a gateway is how reconciliation acts on someone else's order."""
        with pytest.raises(ValueError, match="not gateway-namespaced"):
            ad.split_id("250906000123456")

    def test_rejects_gateway_with_separator(self) -> None:
        with pytest.raises(ValueError):
            ad.namespaced_id("ki:te", "1")

    def test_rejects_empty_parts(self) -> None:
        with pytest.raises(ValueError):
            ad.namespaced_id("kite", "")
        with pytest.raises(ValueError):
            ad.namespaced_id("", "1")


# ── 2. the event vocabulary ───────────────────────────────────────────────────


class TestEventKinds:
    def test_every_kind_is_classified_exactly_once(self) -> None:
        """⭐ The T7 shape: a state in neither set (or both) is a silent mis-file.

        `is_active()` decides whether an order still holds capital, so an unclassified
        kind would make A42's available-cash derivation quietly wrong rather than loud.
        """
        for kind in ad.EventKind:
            in_active = kind in ad.ACTIVE_KINDS
            in_terminal = kind in ad.TERMINAL_KINDS
            assert in_active != in_terminal, (
                f"{kind} must be in exactly one of ACTIVE_KINDS/TERMINAL_KINDS"
            )

    def test_partially_filled_is_active(self) -> None:
        """The remainder can still fill, so it still holds capital."""
        assert ad.is_active(ad.EventKind.PARTIALLY_FILLED)

    def test_denied_is_terminal(self) -> None:
        """Our own refusal never consumes capital."""
        assert not ad.is_active(ad.EventKind.DENIED)

    def test_denied_and_rejected_are_distinct(self) -> None:
        """⭐ Ours vs the broker's — collapsing them destroys the only signal that
        separates 'our rules are too tight' from 'the exchange said no'."""
        assert ad.EventKind.DENIED is not ad.EventKind.REJECTED
        assert ad.EventKind.DENIED.value != ad.EventKind.REJECTED.value

    def test_cancel_requested_still_holds_capital(self) -> None:
        """A cancel that has not been confirmed may still fill."""
        assert ad.is_active(ad.EventKind.CANCEL_REQUESTED)


# ── 3. requests and acks ──────────────────────────────────────────────────────


class TestOrderRequest:
    def test_rejects_non_positive_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity must be positive"):
            ad.OrderRequest(
                client_order_id="paper:1", stock_id=1, symbol="X", side="BUY", quantity=0
            )

    def test_rejects_unknown_side(self) -> None:
        with pytest.raises(ValueError, match="side must be"):
            ad.OrderRequest(
                client_order_id="paper:1", stock_id=1, symbol="X", side="LONG", quantity=1
            )

    def test_limit_order_needs_a_price(self) -> None:
        with pytest.raises(ValueError, match="needs a limit_price"):
            ad.OrderRequest(
                client_order_id="paper:1", stock_id=1, symbol="X", side="BUY",
                quantity=1, order_type="LIMIT",
            )

    def test_carries_no_kite_specific_fields(self) -> None:
        """⚠ `variety`/`validity`/Kite product codes belong in the Kite adapter.

        Put them on the shared type and the 'port' is just Kite's API with an extra
        indirection — the standard way a port stops being one.
        """
        fields = set(ad.OrderRequest.__dataclass_fields__)
        assert fields.isdisjoint({"variety", "validity", "exchange", "tag"})


class TestAckIsNotAFill:
    def test_ack_has_no_fill_fields(self) -> None:
        """⭐ The single most important structural rule in 7.2.

        If an `Ack` could carry a fill, callers would read it as one and the paper
        gateway's synchrony would leak into every call site — met on day 1 of live.
        """
        fields = set(ad.Ack.__dataclass_fields__)
        assert fields.isdisjoint({"filled_qty", "filled_price", "average_price", "fill"})

    def test_rejected_ack_is_still_an_ack(self) -> None:
        """The broker answered. 'No' is an answer, not an exception."""
        ack = ad.Ack(
            client_order_id="paper:1", status=ad.AckStatus.REJECTED, reason="nope"
        )
        assert not ack.accepted
        assert ack.reason == "nope"


class TestErrorClassification:
    def test_unknown_is_not_retryable(self) -> None:
        """⚠ Retrying an order whose fate you do not know is how you get two positions."""
        err = ad.BrokerAdapterError("timed out mid-flight", ad.ErrorClass.UNKNOWN)
        assert not err.retryable

    def test_retryable_is_retryable(self) -> None:
        err = ad.BrokerAdapterError("connection reset", ad.ErrorClass.RETRYABLE)
        assert err.retryable

    def test_terminal_is_not_retryable(self) -> None:
        err = ad.BrokerAdapterError("insufficient funds", ad.ErrorClass.TERMINAL)
        assert not err.retryable


# ── 4. the paper adapter ──────────────────────────────────────────────────────


class TestPaperBrokerAdapter:
    async def test_satisfies_the_port(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        await db.commit()
        _events, sink = _collector()
        assert isinstance(PaperBrokerAdapter(db, user, sink), ad.BrokerAdapter)

    async def test_submit_returns_ack_and_emits_fill_as_an_event(
        self, db: AsyncSession
    ) -> None:
        """⭐ Paper CAN fill synchronously and still must not return the fill."""
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        events, sink = _collector()
        a = PaperBrokerAdapter(db, user, sink)
        ack = await a.submit(
            ad.OrderRequest(
                client_order_id="paper:req-1", stock_id=stock.id, symbol=stock.symbol,
                side="BUY", quantity=10, signal_id=signal.id,
            )
        )
        assert isinstance(ack, ad.Ack)
        assert ack.accepted
        assert ack.broker_order_id is not None
        assert ack.broker_order_id.startswith("paper:")

        kinds = [e.kind for e in events]
        assert kinds == [ad.EventKind.ACCEPTED, ad.EventKind.FILLED]
        fill = events[-1]
        assert fill.payload["filled_qty"] == 10

    async def test_sequence_is_monotonic_per_order(self, db: AsyncSession) -> None:
        """A gap must be detectable, or the projection cannot be trusted."""
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        events, sink = _collector()
        a = PaperBrokerAdapter(db, user, sink)
        await a.submit(
            ad.OrderRequest(
                client_order_id="paper:req-1", stock_id=stock.id, symbol=stock.symbol,
                side="BUY", quantity=10, signal_id=signal.id,
            )
        )
        seqs = [e.seq for e in events if e.client_order_id == "paper:req-1"]
        assert seqs == list(range(1, len(seqs) + 1))

    async def test_refusal_is_an_ack_not_an_exception(self, db: AsyncSession) -> None:
        """⭐ The distinction 7.3's FSM is built on.

        A through-stop order is the paper analogue of a broker rejection: the request
        landed and was refused on its merits. It must come back as a REJECTED ack with
        a reason, not as an exception the caller has to catch — otherwise the FSM has no
        `rejected` transition to record and the refusal leaves no trace, which is the
        1.1 problem 7.0 identified.
        """
        user = await _make_user(db)
        stock = await make_stock(db)
        # Entry BELOW its own stop ⇒ the broker's unconditional through-stop rejection.
        signal = await _make_signal(db, stock.id, entry="470.0000", sl="480.0000")
        await db.commit()

        events, sink = _collector()
        a = PaperBrokerAdapter(db, user, sink)
        ack = await a.submit(
            ad.OrderRequest(
                client_order_id="paper:req-bad", stock_id=stock.id, symbol=stock.symbol,
                side="BUY", quantity=10, signal_id=signal.id,
            )
        )
        assert not ack.accepted
        assert ack.reason
        assert [e.kind for e in events] == [ad.EventKind.REJECTED]
        assert events[0].payload["error_class"] == ad.ErrorClass.TERMINAL.value

    async def test_missing_signal_is_rejected_not_raised(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        await db.commit()

        events, sink = _collector()
        a = PaperBrokerAdapter(db, user, sink)
        ack = await a.submit(
            ad.OrderRequest(
                client_order_id="paper:req-x", stock_id=stock.id, symbol=stock.symbol,
                side="BUY", quantity=10,
                signal_id="00000000-0000-0000-0000-000000000000",
            )
        )
        assert not ack.accepted
        assert [e.kind for e in events] == [ad.EventKind.REJECTED]

    async def test_cancel_answers_honestly(self, db: AsyncSession) -> None:
        """A caller that believes it cancelled something is worse off than one told
        it could not."""
        user = await _make_user(db)
        await db.commit()
        _events, sink = _collector()
        a = PaperBrokerAdapter(db, user, sink)
        ack = await a.cancel("paper:whatever")
        assert not ack.accepted
        assert "nothing to cancel" in (ack.reason or "")

    async def test_open_orders_is_empty_for_paper(self, db: AsyncSession) -> None:
        """⚠ And 7.4 must not read this as evidence reconciliation works."""
        user = await _make_user(db)
        await db.commit()
        _events, sink = _collector()
        assert await PaperBrokerAdapter(db, user, sink).fetch_open_orders() == []

    async def test_positions_sign_shorts_negative(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        db.add(
            Position(
                user_id=user.id, stock_id=stock.id, mode="paper", side="SHORT",
                quantity=40, avg_entry_price=Decimal("500"), realized_pnl=Decimal("0"),
                opened_at=datetime.now(tz=UTC),
            )
        )
        await db.commit()

        _events, sink = _collector()
        positions = await PaperBrokerAdapter(db, user, sink).fetch_positions()
        assert len(positions) == 1
        assert positions[0].quantity == -40, "a broker reports a net position, signed"

    async def test_funds_deducts_open_exposure(self, db: AsyncSession) -> None:
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        db.add(
            Position(
                user_id=user.id, stock_id=stock.id, mode="paper", side="LONG",
                quantity=100, avg_entry_price=Decimal("500"), realized_pnl=Decimal("0"),
                opened_at=datetime.now(tz=UTC),
            )
        )
        await db.commit()

        _events, sink = _collector()
        funds = await PaperBrokerAdapter(db, user, sink).fetch_funds()
        assert funds.used == Decimal("50000")
        assert funds.available == Decimal("50000")
