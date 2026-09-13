"""U17 (2026-09-14) — the universe is an ENTRY gate, not a visibility gate.

REGRESSION. `_build_token_stock_map` filtered `s.is_active = true`, and that map
is the subscription universe. Everything an open position depends on hangs off it:

    subscription -> tick -> ltp:{stock_id} -> position_monitor.scan_positions
                                           -> SL / TP / trail / exit

`scan_positions` is correctly NOT universe-filtered, but it prices from
`get_live_ltp`, and that key exists only for SUBSCRIBED instruments. So a held
name that left the active set stopped receiving ticks, its key expired at 600s,
and the monitor skipped it PERMANENTLY — stop-loss and target still recorded on
the row, and nothing alive to evaluate them. The skip is silent by design: "the
monitor never acts on a stale price."

Latent until now only because `is_active` moves when a human runs a script. D2′
makes a rule re-evaluate it NIGHTLY, so this is a precondition for that change.

Every test here fails on the pre-U17 query.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.broker.tick_consumer import _build_token_stock_map, held_without_instrument
from app.models.broker import KiteInstrument
from app.models.trading import Position
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock


async def _instrument(db: AsyncSession, token: int, symbol: str) -> None:
    db.add(
        KiteInstrument(
            instrument_token=token,
            exchange_token=token >> 8,
            tradingsymbol=symbol,
            exchange="NSE",
            instrument_type="EQ",
            name=f"{symbol} Ltd",
            last_price=Decimal("100"),
            tick_size=Decimal("0.05"),
            lot_size=1,
            segment="NSE",
            expiry="",
            strike=Decimal("0"),
            synced_at=datetime.now(tz=UTC),
        )
    )


async def _open_position(db: AsyncSession, user_id: int, stock_id: int) -> Position:
    pos = Position(
        id=str(uuid.uuid4()),
        user_id=user_id,
        stock_id=stock_id,
        mode="paper",
        side="LONG",
        quantity=10,
        avg_entry_price=Decimal("100.0000"),
        opened_at=datetime.now(tz=UTC),
        closed_at=None,
    )
    db.add(pos)
    return pos


class TestHeldNamesAreAlwaysSubscribed:
    async def test_an_inactive_name_we_hold_is_subscribed(self, db: AsyncSession) -> None:
        """The exact hazard: the position is open, the flag says inactive, and
        without the union the monitor goes blind on it forever."""
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="HELDCO", is_active=False)
        await _instrument(db, 9001, "HELDCO")
        await _open_position(db, user.id, stock.id)
        await db.commit()

        token_map = await _build_token_stock_map(db, "tok")

        assert token_map.get(9001) == stock.id  # old query: absent

    async def test_an_inactive_name_we_do_not_hold_stays_out(
        self, db: AsyncSession
    ) -> None:
        """The union must not become 'subscribe to everything' — the universe is
        still the entry gate, and U16 caps the connection at 3,000."""
        await make_stock(db, symbol="DORMANT", is_active=False)
        await _instrument(db, 9002, "DORMANT")
        await db.commit()

        assert 9002 not in await _build_token_stock_map(db, "tok")

    async def test_an_active_name_is_subscribed_as_before(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="LIVECO", is_active=True)
        await _instrument(db, 9003, "LIVECO")
        await db.commit()

        assert (await _build_token_stock_map(db, "tok")).get(9003) == stock.id

    async def test_a_closed_position_does_not_hold_a_slot(self, db: AsyncSession) -> None:
        """Once flat, the name goes back to being a universe question."""
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="EXITEDCO", is_active=False)
        await _instrument(db, 9004, "EXITEDCO")
        pos = await _open_position(db, user.id, stock.id)
        pos.closed_at = datetime.now(tz=UTC)
        await db.commit()

        assert 9004 not in await _build_token_stock_map(db, "tok")

    async def test_a_live_mode_position_counts_too(self, db: AsyncSession) -> None:
        """Mode-agnostic on purpose: a Phase-7 LIVE position needs its feed even
        more than a paper one does."""
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="LIVEPOS", is_active=False)
        await _instrument(db, 9005, "LIVEPOS")
        pos = await _open_position(db, user.id, stock.id)
        pos.mode = "live"
        await db.commit()

        assert (await _build_token_stock_map(db, "tok")).get(9005) == stock.id

    async def test_a_held_name_is_not_double_counted(self, db: AsyncSession) -> None:
        """An ACTIVE name we also hold must appear once — two open positions in
        the same stock must not duplicate a subscription slot."""
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="BOTHCO", is_active=True)
        await _instrument(db, 9006, "BOTHCO")
        await _open_position(db, user.id, stock.id)
        await _open_position(db, user.id, stock.id)
        await db.commit()

        token_map = await _build_token_stock_map(db, "tok")
        assert list(token_map.values()).count(stock.id) == 1


class TestStrandedPositions:
    """The union cannot rescue a held name with no EQ instrument at all — there is
    no token to subscribe to. Those are reported so a human can act, never raised:
    one stranded name must not stop the worker serving every other position."""

    async def test_a_held_name_with_no_instrument_is_reported(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="GHOSTCO", is_active=False)
        await _open_position(db, user.id, stock.id)  # no kite_instruments row
        await db.commit()

        assert await held_without_instrument(db) == [(stock.id, "GHOSTCO")]

    async def test_a_subscribable_held_name_is_not_reported(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="FINECO", is_active=False)
        await _instrument(db, 9007, "FINECO")
        await _open_position(db, user.id, stock.id)
        await db.commit()

        assert await held_without_instrument(db) == []

    async def test_a_closed_position_is_not_reported(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="OLDCO", is_active=False)
        pos = await _open_position(db, user.id, stock.id)
        pos.closed_at = datetime.now(tz=UTC)
        await db.commit()

        assert await held_without_instrument(db) == []
