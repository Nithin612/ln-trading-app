"""Phase 7.3 — the order path writes its event stream.

The test this file exists for is `test_denial_survives_the_exception`.

Everything else here would pass just as well if the denial row were written and then
silently rolled back by the session teardown that follows an `HTTPException` — and a
rolled-back denial is exactly the failure the whole `order_events` table was built to
prevent, in exactly the branch nobody exercises by hand.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.broker import event_store, order_fsm
from app.broker.adapter import EventKind
from app.models.signal import Signal
from app.models.trading import OrderEventRow, Position
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_FACTORS = {
    "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
    "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
}


async def _make_signal(
    db: AsyncSession,
    stock_id: int,
    *,
    entry: str = "500.0000",
    sl: str = "480.0000",
    factors: dict | None = None,
) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit="540.0000", suggested_qty=100,
        confidence_pct=80, factor_scores=factors or _FACTORS,
        headline="BUY EVENTS", status="active",
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _events(db: AsyncSession, user_id: int) -> list[OrderEventRow]:
    return list(
        (
            await db.execute(
                select(OrderEventRow)
                .where(OrderEventRow.user_id == user_id)
                .order_by(OrderEventRow.seq)
            )
        )
        .scalars()
        .all()
    )


class TestOrderPathWritesItsStream:
    async def test_success_writes_submitted_accepted_filled(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 201

        rows = await _events(db, user.id)
        assert [e.kind for e in rows] == [
            EventKind.SUBMITTED.value,
            EventKind.ACCEPTED.value,
            EventKind.FILLED.value,
        ]
        assert [e.seq for e in rows] == [1, 2, 3], "gapless, monotonic, from 1"
        assert rows[0].client_order_id.startswith("paper:")
        assert len({e.client_order_id for e in rows}) == 1, "one stream, one order"
        assert rows[-1].payload["filled_qty"] > 0

    async def test_denial_survives_the_exception(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⭐ THE test. `get_db` rolls back when a handler raises.

        Without an explicit commit before `raise HTTPException`, the denial row is
        written and then discarded — the record of what the risk layer refused
        disappears in precisely the branch it exists to capture, and every other test in
        this file still passes.

        Driven through the ACTIVE entry-diversity gate (a single-factor signal), so this
        is a real refusal on a live rule rather than a contrived one.
        """
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(
            db, stock.id,
            factors={"RSI_DIVERGENCE": {"weight": 20, "score": 0.8, "explanation": "solo"}},
        )
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 409

        rows = await _events(db, user.id)
        assert [e.kind for e in rows] == [
            EventKind.SUBMITTED.value,
            EventKind.DENIED.value,
        ], "the denial must still be on disk after the 409"
        denial = rows[-1]
        assert denial.payload["rule"] == "eligibility"
        assert denial.payload["reason"], "the reason travels with the refusal"
        assert denial.payload["reason"] == r.json()["detail"], (
            "the recorded reason and the one the caller saw must be the same words"
        )

    async def test_breaker_denial_is_recorded_with_its_rule(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A denial names WHICH rule refused — that is what a report groups by."""
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        now = datetime.now(tz=UTC)
        db.add(
            Position(
                user_id=user.id, stock_id=stock.id, mode="paper", side="LONG",
                quantity=100, avg_entry_price=Decimal("500"), current_sl=Decimal("480"),
                realized_pnl=Decimal("-99999"), opened_at=now, closed_at=now,
                signal_id=signal.id,
            )
        )
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 409

        rows = await _events(db, user.id)
        assert rows[-1].kind == EventKind.DENIED.value
        assert rows[-1].payload["rule"] == "circuit_breaker"

    async def test_missing_signal_is_recorded_too(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Even a 404 leaves a trail: someone tried to trade an id that does not exist,
        and that is worth knowing about."""
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert r.status_code == 404

        rows = await _events(db, user.id)
        assert [e.kind for e in rows] == [
            EventKind.SUBMITTED.value,
            EventKind.DENIED.value,
        ]
        assert rows[-1].payload["rule"] == "signal_missing"
        assert rows[-1].stock_id is None, "no signal, so no stock to attribute it to"

    async def test_broker_refusal_is_rejected_not_denied(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⭐ The distinction that makes the record readable.

        A through-stop entry is the broker's own unconditional pre-fill refusal — the
        paper analogue of an exchange saying no. Recording it as `denied` would blame our
        thresholds for something the market did, and no later analysis could separate them.
        """
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        # Entry BELOW its own stop.
        signal = await _make_signal(db, stock.id, entry="470.0000", sl="480.0000")
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 422

        rows = await _events(db, user.id)
        assert [e.kind for e in rows] == [
            EventKind.SUBMITTED.value,
            EventKind.REJECTED.value,
        ], "the broker refused, so it is REJECTED — not our DENIED"
        assert rows[-1].payload["error_class"] == "terminal"


class TestStreamRoundTrip:
    async def test_a_real_order_projects_to_filled(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The seam: what the endpoint wrote must fold into the state the FSM reports.

        This is 7.4's restart recovery in miniature — `load_events` → `project` — so if
        the endpoint ever emits an illegal sequence, this fails rather than 7.4 failing
        months later against a real broker.
        """
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 201

        rows = await _events(db, user.id)
        events = await event_store.load_events(db, rows[0].client_order_id)
        state = order_fsm.project(events)  # strict: any illegal transition raises here

        assert state.kind is EventKind.FILLED
        assert state.terminal and not state.active
        assert state.filled_qty == r.json()["filled_qty"]
        assert state.broker_order_id is not None

    async def test_refusals_between_finds_what_was_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⭐ The question the table was built to answer, asked end to end.

        Before the event stream this returned nothing at all, because a refusal wrote
        nothing at all.
        """
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        blocked = await _make_signal(
            db, stock.id,
            factors={"RSI_DIVERGENCE": {"weight": 20, "score": 0.8, "explanation": "solo"}},
        )
        ok = await _make_signal(db, stock.id)
        await db.commit()

        start = datetime.now(tz=UTC) - timedelta(minutes=1)
        for sig in (blocked, ok):
            await client.post(
                "/api/v1/trading/orders",
                json={"signal_id": sig.id, "side": "BUY"},
                headers=headers,
            )
        end = datetime.now(tz=UTC) + timedelta(minutes=1)

        refusals = await event_store.refusals_between(
            db, user_id=user.id, start=start, end=end
        )
        assert len(refusals) == 1, "one refused, one filled"
        assert refusals[0].kind == EventKind.DENIED.value
        assert refusals[0].signal_id == blocked.id


class TestEventStore:
    async def test_sequence_starts_at_one_and_increments(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        await db.commit()
        assert await event_store.next_seq(db, "paper:x") == 1
        await event_store.append(
            db, client_order_id="paper:x", kind=EventKind.SUBMITTED, user_id=user.id
        )
        assert await event_store.next_seq(db, "paper:x") == 2

    async def test_duplicate_sequence_is_refused_by_name(self, db: AsyncSession) -> None:
        """The UNIQUE constraint is the integrity rule; the named exception is so a
        caller can tell a concurrency bug from an opaque database failure."""
        user = await create_test_user(db)
        await db.commit()
        await event_store.append(
            db, client_order_id="paper:y", kind=EventKind.SUBMITTED, user_id=user.id, seq=1
        )
        try:
            await event_store.append(
                db, client_order_id="paper:y", kind=EventKind.DENIED, user_id=user.id, seq=1
            )
        except event_store.DuplicateSequenceError as exc:
            assert "already has seq 1" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("a duplicate (order, seq) must be refused")

    async def test_unknown_kind_refuses_to_project(self, db: AsyncSession) -> None:
        """A row we cannot interpret means a PARTIAL stream. A confidently wrong order
        state is worse than a loud stop."""
        user = await create_test_user(db)
        db.add(
            OrderEventRow(
                client_order_id="paper:z", seq=1, kind="teleported",
                at=datetime.now(tz=UTC), user_id=user.id, payload={},
            )
        )
        await db.commit()
        try:
            await event_store.load_events(db, "paper:z")
        except ValueError as exc:
            assert "unknown kind" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("an uninterpretable row must not be silently skipped")
