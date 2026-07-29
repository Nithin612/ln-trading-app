"""Integration tests for Phase 8 — paper trading.

Covers:
  - Position lifecycle: open → unrealized P&L → close → realized P&L
  - Circuit breaker: blocks new orders when daily loss or trade count exceeded
  - Trail SL state machine: unit tests (no DB needed)
  - API endpoints: orders, positions, close, update-sl, history, daily-pnl
  - SL and TP auto-close logic (via paper broker directly)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.models.user import User
from app.trading.fees import roundtrip_charges
from app.trading.trail_sl import advance_trail, compute_pnl, is_sl_hit, is_tp_hit
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


def _net(side: str, entry: str, exit_: str, qty: int, product: str = "delivery") -> Decimal:
    """Expected NET realized P&L = gross − round-trip charges (source of truth
    is fees.py, so this tracks the schedule rather than a brittle constant)."""
    gross = compute_pnl(side=side, entry=Decimal(entry), exit_price=Decimal(exit_), quantity=qty)
    charges, _ = roundtrip_charges(
        position_side=side,
        entry_price=Decimal(entry),
        exit_price=Decimal(exit_),
        quantity=qty,
        product=product,
    )
    return gross - charges

# ── Factories ────────────────────────────────────────────────────────────────

async def _make_user(
    db: AsyncSession,
    email: str = "trader@example.com",
    capital: Decimal = Decimal("100000"),
    daily_loss_pct: Decimal = Decimal("3.00"),
    max_trades: int = 2,
    allow_offmarket_entry: bool = True,  # tests fill without a live market
) -> User:
    from app.core.security import hash_password

    user = User(
        email=email,
        password_hash=hash_password("pass123"),
        full_name="Trader",
        role="user",
        is_active=True,
        trading_mode="paper",
        capital_inr=capital,
        daily_loss_limit_pct=daily_loss_pct,
        max_trades_per_day=max_trades,
        allow_offmarket_entry=allow_offmarket_entry,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_signal(
    db: AsyncSession,
    stock_id: int,
    direction: str = "BUY",
    entry: str = "500.0000",
    sl: str = "480.0000",
    tp: str = "540.0000",
    qty: int = 100,
) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction=direction,
        classification="swing",
        timeframe="1d",
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        suggested_qty=qty,
        confidence_pct=80,
        factor_scores={"DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"}},
        headline=f"{direction} TEST@{entry}",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _open_position(
    db: AsyncSession,
    user: User,
    stock: Stock,
    signal: Signal,
    side: str = "LONG",
    entry: Decimal = Decimal("500"),
    sl: Decimal = Decimal("480"),
    tp: Decimal = Decimal("540"),
    qty: int = 100,
    opened_at: datetime | None = None,
) -> Position:
    pos = Position(
        user_id=user.id,
        stock_id=stock.id,
        mode="paper",
        side=side,
        quantity=qty,
        avg_entry_price=entry,
        current_sl=sl,
        current_tp=tp,
        trail_state="none",
        unrealized_pnl=Decimal("0"),
        realized_pnl=Decimal("0"),
        opened_at=opened_at or datetime.now(tz=UTC),
        signal_id=signal.id,
    )
    db.add(pos)
    await db.flush()
    return pos


async def _closed_position(
    db: AsyncSession,
    user: User,
    stock: Stock,
    signal: Signal,
    realized_pnl: Decimal,
    closed_at: datetime | None = None,
) -> Position:
    pos = await _open_position(db, user, stock, signal)
    pos.realized_pnl = realized_pnl
    pos.closed_at = closed_at or datetime.now(tz=UTC)
    await db.flush()
    return pos


# ── Trail SL unit tests (pure logic, no DB) ───────────────────────────────────

class TestTrailSl:
    def test_no_advance_when_price_below_1r(self) -> None:
        r = advance_trail(
            side="LONG",
            entry=Decimal("500"),
            original_sl=Decimal("480"),  # R = 20
            current_sl=Decimal("480"),
            current_price=Decimal("515"),  # 0.75R move
            current_state="none",
        )
        assert not r.advanced
        assert r.new_state == "none"
        assert r.new_sl == Decimal("480")

    def test_advance_to_breakeven_at_1r(self) -> None:
        r = advance_trail(
            side="LONG",
            entry=Decimal("500"),
            original_sl=Decimal("480"),  # R = 20
            current_sl=Decimal("480"),
            current_price=Decimal("522"),  # 1.1R
            current_state="none",
        )
        assert r.advanced
        assert r.new_state == "breakeven"
        assert r.new_sl == Decimal("500")  # breakeven = entry

    def test_advance_to_trailing_1_at_1_5r(self) -> None:
        r = advance_trail(
            side="LONG",
            entry=Decimal("500"),
            original_sl=Decimal("480"),
            current_sl=Decimal("500"),
            current_price=Decimal("532"),  # 1.6R
            current_state="breakeven",
        )
        assert r.advanced
        assert r.new_state == "trailing_1"
        # SL = entry + 0.5R = 500 + 10 = 510
        assert r.new_sl == Decimal("510")

    def test_advance_to_trailing_2_at_2r(self) -> None:
        r = advance_trail(
            side="LONG",
            entry=Decimal("500"),
            original_sl=Decimal("480"),
            current_sl=Decimal("510"),
            current_price=Decimal("545"),  # 2.25R
            current_state="trailing_1",
        )
        assert r.advanced
        assert r.new_state == "trailing_2"
        # SL = current_price - R = 545 - 20 = 525
        assert r.new_sl == Decimal("525")

    def test_no_regression_from_higher_state(self) -> None:
        # Price drops but we've already hit trailing_1 → no state regression
        r = advance_trail(
            side="LONG",
            entry=Decimal("500"),
            original_sl=Decimal("480"),
            current_sl=Decimal("510"),
            current_price=Decimal("516"),  # just above trailing_1 territory
            current_state="trailing_1",
        )
        assert not r.advanced
        assert r.new_state == "trailing_1"

    def test_short_position_breakeven(self) -> None:
        r = advance_trail(
            side="SHORT",
            entry=Decimal("500"),
            original_sl=Decimal("520"),  # R = 20
            current_sl=Decimal("520"),
            current_price=Decimal("478"),  # 1.1R favorable
            current_state="none",
        )
        assert r.advanced
        assert r.new_state == "breakeven"
        assert r.new_sl == Decimal("500")

    def test_sl_hit_long(self) -> None:
        assert is_sl_hit(side="LONG", current_price=Decimal("479"), current_sl=Decimal("480"))
        assert not is_sl_hit(side="LONG", current_price=Decimal("481"), current_sl=Decimal("480"))

    def test_tp_hit_long(self) -> None:
        assert is_tp_hit(side="LONG", current_price=Decimal("541"), current_tp=Decimal("540"))
        assert not is_tp_hit(side="LONG", current_price=Decimal("539"), current_tp=Decimal("540"))

    def test_compute_pnl_long_profit(self) -> None:
        pnl = compute_pnl(
            side="LONG", entry=Decimal("500"), exit_price=Decimal("540"), quantity=100
        )
        assert pnl == Decimal("4000")

    def test_compute_pnl_long_loss(self) -> None:
        pnl = compute_pnl(
            side="LONG", entry=Decimal("500"), exit_price=Decimal("480"), quantity=100
        )
        assert pnl == Decimal("-2000")

    def test_compute_pnl_short_profit(self) -> None:
        pnl = compute_pnl(
            side="SHORT", entry=Decimal("500"), exit_price=Decimal("460"), quantity=100
        )
        assert pnl == Decimal("4000")


# ── Circuit breaker unit tests ─────────────────────────────────────────────────

class TestCircuitBreaker:
    async def test_triggers_on_daily_loss_breach(self, db: AsyncSession) -> None:
        from app.trading.circuit_breaker import check_circuit_breaker

        user = await _make_user(
            db, capital=Decimal("100000"), daily_loss_pct=Decimal("3.00"), max_trades=10
        )
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        # Inject closed position with realized loss > 3% of 100k = ₹3000
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("-3500"))
        await db.commit()

        triggered, reason = await check_circuit_breaker(db, user)
        assert triggered
        assert "Daily loss limit reached" in reason

    async def test_no_trigger_within_limit(self, db: AsyncSession) -> None:
        from app.trading.circuit_breaker import check_circuit_breaker

        user = await _make_user(
            db, capital=Decimal("100000"), daily_loss_pct=Decimal("3.00"), max_trades=10
        )
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("-1000"))
        await db.commit()

        triggered, _ = await check_circuit_breaker(db, user)
        assert not triggered

    async def test_triggers_on_max_trades_exceeded(self, db: AsyncSession) -> None:
        from app.trading.circuit_breaker import check_circuit_breaker

        user = await _make_user(
            db, capital=Decimal("100000"), daily_loss_pct=Decimal("3.00"), max_trades=2
        )
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)

        # 2 trades taken today (profitable, so no loss limit)
        now = datetime.now(tz=UTC)
        for _ in range(2):
            pos = Position(
                user_id=user.id,
                stock_id=stock.id,
                mode="paper",
                side="LONG",
                quantity=10,
                avg_entry_price=Decimal("500"),
                trail_state="none",
                realized_pnl=Decimal("0"),
                opened_at=now,
                signal_id=signal.id,
            )
            db.add(pos)
        await db.commit()

        triggered, reason = await check_circuit_breaker(db, user)
        assert triggered
        assert "Max trades per day" in reason


# ── Paper broker integration tests ─────────────────────────────────────────────

class TestPaperBroker:
    async def test_place_and_close_position(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import close_position, place_paper_order

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")

        order, pos = await place_paper_order(db, user, signal, side="BUY", quantity=100)
        await db.commit()

        assert order.status == "filled"
        assert order.filled_qty == 100
        assert pos.side == "LONG"
        assert pos.quantity == 100
        assert pos.closed_at is None

        close_order, closed_pos = await close_position(
            db, pos, exit_price=Decimal("540"), reason="test"
        )
        await db.commit()

        assert closed_pos.closed_at is not None
        # realized_pnl is NET of round-trip costs (was gross ₹4000)
        assert closed_pos.realized_pnl == _net("LONG", "500", "540", 100)
        assert closed_pos.charges is not None and closed_pos.charges > Decimal("0")
        # gross is recoverable
        assert closed_pos.realized_pnl + closed_pos.charges == Decimal("4000")

    async def test_average_in_existing_position(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import place_paper_order

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")

        # First entry: 100 shares @ 500
        _, pos1 = await place_paper_order(db, user, signal, side="BUY", quantity=100)
        # Second entry: 100 shares @ 500 → avg should stay 500
        _, pos2 = await place_paper_order(db, user, signal, side="BUY", quantity=100)
        await db.commit()

        assert pos1.id == pos2.id  # same position averaged in
        assert pos2.quantity == 200

    async def test_sl_hit_closes_at_sl_price(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import close_position

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000")
        pos = await _open_position(
            db, user, stock, signal, entry=Decimal("500"), sl=Decimal("480")
        )

        _order, closed_pos = await close_position(
            db, pos, exit_price=Decimal("480"), reason="sl_hit"
        )
        await db.commit()

        # (480-500)*100 = -2000 gross, minus costs
        assert closed_pos.realized_pnl == _net("LONG", "500", "480", 100)

    async def test_tp_hit_closes_at_tp_price(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import close_position

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", tp="540.0000")
        pos = await _open_position(
            db, user, stock, signal, entry=Decimal("500"), tp=Decimal("540")
        )

        _order, closed_pos = await close_position(
            db, pos, exit_price=Decimal("540"), reason="tp_hit"
        )
        await db.commit()

        assert closed_pos.realized_pnl == _net("LONG", "500", "540", 100)

    async def test_close_already_closed_raises(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import close_position

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        _order, closed_pos = await close_position(db, pos, exit_price=Decimal("510"))
        await db.commit()

        with pytest.raises(ValueError, match="already closed"):
            await close_position(db, closed_pos, exit_price=Decimal("510"))

    async def test_close_records_exit_price_and_reason(self, db: AsyncSession) -> None:
        """Exit facts are denormalised onto the position for Trade History."""
        from app.broker.paper_broker import close_position

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", tp="540.0000")
        pos = await _open_position(db, user, stock, signal, entry=Decimal("500"))

        assert pos.exit_price is None and pos.exit_reason is None  # open
        close_order, closed = await close_position(
            db, pos, exit_price=Decimal("540"), reason="tp_hit"
        )
        await db.commit()

        assert closed.exit_reason == "tp_hit"
        assert closed.exit_price == close_order.filled_price == Decimal("540.0000")

    async def test_update_position_pnl_is_net_and_returns_price(
        self, db: AsyncSession
    ) -> None:
        """Open-position P&L is NET of estimated round-trip costs (so it reads in
        the same units as a closed trade's realized_pnl) and returns the price
        it used (the caller reuses it as the current market price)."""
        from app.broker.paper_broker import update_position_pnl

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")  # swing→delivery
        pos = await _open_position(db, user, stock, signal, entry=Decimal("500"), qty=100)

        used = await update_position_pnl(db, pos, price=Decimal("540"))
        assert used == Decimal("540")
        # net = gross 4000 − estimated round-trip delivery charges
        est, _ = roundtrip_charges(
            position_side="LONG",
            entry_price=Decimal("500"),
            exit_price=Decimal("540"),
            quantity=100,
            product="delivery",
        )
        assert est > Decimal("0")
        assert pos.unrealized_pnl == Decimal("4000") - est


# ── API endpoint tests ─────────────────────────────────────────────────────────

class TestTradingApi:
    async def test_place_order_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/api/v1/trading/orders", json={"signal_id": "bad-id"})
        assert r.status_code == 401

    async def test_place_order_signal_not_found(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert r.status_code == 404

    async def test_place_order_creates_position(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
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
        data = r.json()
        assert data["status"] == "filled"
        assert data["mode"] == "paper"
        assert data["side"] == "BUY"

    async def test_place_order_blocked_by_circuit_breaker(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        # Inject loss exceeding limit
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("-4000"))
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 409
        assert "Daily loss limit" in r.json()["detail"]

    async def test_list_open_positions(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal)
        await db.commit()

        r = await client.get("/api/v1/trading/positions", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["positions"][0]["side"] == "LONG"

    async def test_list_open_positions_reports_current_price(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The open-positions list carries the live market price for display."""
        import redis.asyncio as aioredis
        from app.broker.tick_consumer import LTP_KEY
        from app.core.config import settings

        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal)
        await db.commit()

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = LTP_KEY.format(stock_id=stock.id)
        try:
            await r.set(key, "515.50", ex=600)
            resp = await client.get("/api/v1/trading/positions", headers=headers)
            assert resp.status_code == 200
            row = resp.json()["positions"][0]
            assert Decimal(row["current_price"]) == Decimal("515.50")
        finally:
            await r.delete(key)
            await r.aclose()

    async def test_close_position_endpoint(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        await db.commit()

        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={"exit_price": "540.0000"},
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["closed_at"] is not None
        assert Decimal(data["realized_pnl"]) == _net("LONG", "500", "540", 100)
        assert Decimal(data["charges"]) > Decimal("0")

    async def test_close_already_closed_returns_409(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        pos.closed_at = datetime.now(tz=UTC)
        await db.commit()

        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={},
            headers=headers,
        )
        assert r.status_code == 409

    async def test_update_sl_long_position(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000")
        pos = await _open_position(
            db, user, stock, signal, entry=Decimal("500"), sl=Decimal("480")
        )
        await db.commit()

        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/update-sl",
            json={"new_sl": "490.0000"},
            headers=headers,
        )
        assert r.status_code == 200
        assert Decimal(r.json()["current_sl"]) == Decimal("490")

    async def test_update_sl_invalid_direction_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")
        pos = await _open_position(db, user, stock, signal, entry=Decimal("500"))
        await db.commit()

        # For LONG, SL must be below entry (500) — this should be rejected
        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/update-sl",
            json={"new_sl": "510.0000"},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_trade_history(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("2000"))
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("-1000"))
        await db.commit()

        r = await client.get("/api/v1/trading/history", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2

    async def test_daily_pnl_endpoint(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("1500"))
        await db.commit()

        r = await client.get("/api/v1/trading/daily-pnl", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "realized_pnl" in data
        assert "circuit_breaker_triggered" in data
        assert data["circuit_breaker_triggered"] is False

    async def test_daily_pnl_shows_circuit_breaker_active(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, realized_pnl=Decimal("-4000"))
        await db.commit()

        r = await client.get("/api/v1/trading/daily-pnl", headers=headers)
        assert r.status_code == 200
        assert r.json()["circuit_breaker_triggered"] is True

    async def test_cannot_access_other_users_position(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from app.core.security import hash_password

        user1 = await create_test_user(db, email="u1@example.com")
        user2 = User(
            email="u2@example.com",
            password_hash=hash_password("pass123"),
            full_name="U2",
            role="user",
            is_active=True,
            trading_mode="paper",
        )
        db.add(user2)
        await db.flush()

        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user1, stock, signal)
        await db.commit()

        # User2 tries to close user1's position
        headers2 = await get_auth_headers(client, email="u2@example.com", password="pass123")
        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={},
            headers=headers2,
        )
        assert r.status_code == 404

    async def test_open_positions_not_visible_after_close(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        await db.commit()

        # Close it
        await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={"exit_price": "510.0000"},
            headers=headers,
        )

        # Now open positions should be empty
        r = await client.get("/api/v1/trading/positions", headers=headers)
        assert r.json()["total"] == 0

    async def test_validate_order_side(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "HOLD"},
            headers=headers,
        )
        assert r.status_code == 422


# ── Sizing from user capital + cost model ──────────────────────────────────────

class TestSizingAndCosts:
    async def test_sizes_from_user_capital_not_suggested_qty(self, db: AsyncSession) -> None:
        """No explicit quantity → size from THIS user's capital/risk, never the
        signal's house-default suggested_qty."""
        from app.analysis.risk import compute_quantity
        from app.broker.paper_broker import place_paper_order

        user = await _make_user(db, capital=Decimal("100000"))  # 2% risk default
        stock = await make_stock(db)
        # suggested_qty deliberately bogus (sized to a ₹5L house default)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000", qty=999)

        _order, pos = await place_paper_order(db, user, signal, side="BUY", quantity=None)
        await db.commit()

        expected = compute_quantity(
            Decimal("100000"), Decimal("2.00"), Decimal("500"), Decimal("480")
        )
        assert expected == 100  # ₹2000 risk / ₹20 per share
        assert pos.quantity == expected
        assert pos.quantity != 999  # did NOT use suggested_qty

    async def test_explicit_quantity_override_honored(self, db: AsyncSession) -> None:
        from app.broker.paper_broker import place_paper_order

        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000")
        _order, pos = await place_paper_order(db, user, signal, side="BUY", quantity=7)
        await db.commit()
        assert pos.quantity == 7

    async def test_zero_size_rejected_not_clamped(self, db: AsyncSession) -> None:
        """Stop wider than the account's per-trade risk → reject (never a
        0-qty or 1-share clamp)."""
        from app.broker.paper_broker import PaperOrderError, place_paper_order

        user = await _make_user(db, capital=Decimal("100"))  # ₹2 risk budget
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000")  # ₹20/share
        with pytest.raises(PaperOrderError, match="rounds to 0"):
            await place_paper_order(db, user, signal, side="BUY", quantity=None)

    async def test_api_rejects_zero_size_422(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        user.capital_inr = Decimal("100")  # tiny account
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000", sl="480.0000")
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 422
        assert "rounds to 0" in r.json()["detail"]

    async def test_costs_disabled_returns_gross(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.broker.paper_broker import close_position
        from app.core.config import settings

        monkeypatch.setattr(settings, "paper_costs_enabled", False)
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal, entry=Decimal("500"))
        _order, closed = await close_position(db, pos, exit_price=Decimal("540"))
        await db.commit()
        assert closed.realized_pnl == Decimal("4000")  # gross, no costs
        assert closed.charges == Decimal("0")

    async def test_short_position_net_pnl(self, db: AsyncSession) -> None:
        """A SHORT nets costs too; charges are symmetric to the long side."""
        from app.broker.paper_broker import close_position

        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, direction="SELL")
        pos = await _open_position(
            db, user, stock, signal, side="SHORT", entry=Decimal("500"), sl=Decimal("520")
        )
        _order, closed = await close_position(db, pos, exit_price=Decimal("460"))
        await db.commit()
        assert closed.realized_pnl == _net("SHORT", "500", "460", 100)
        assert closed.charges is not None and closed.charges > Decimal("0")

    async def test_offmarket_entry_rejected_without_live_ltp(self, db: AsyncSession) -> None:
        """Default (guard on): no live tick price → reject (would fill at a
        stale close)."""
        from app.broker.paper_broker import PaperOrderError, get_live_ltp, place_paper_order

        user = await _make_user(db, allow_offmarket_entry=False)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        assert await get_live_ltp(stock.id) is None  # no tick set → off-market
        with pytest.raises(PaperOrderError, match="No live market price"):
            await place_paper_order(db, user, signal, side="BUY", quantity=100)

    async def test_offmarket_entry_allowed_when_opted_in(self, db: AsyncSession) -> None:
        """Guard off → off-market entry allowed (fills at the daily-close fallback)."""
        from app.broker.paper_broker import place_paper_order

        user = await _make_user(db, allow_offmarket_entry=True)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")
        _order, pos = await place_paper_order(db, user, signal, side="BUY", quantity=100)
        await db.commit()
        assert pos.quantity == 100  # placed; fell back to signal entry (no LTP, no daily bar)

    async def test_entry_allowed_with_live_ltp_fills_at_ltp(self, db: AsyncSession) -> None:
        """Guard on, but a live tick exists → allowed and fills at the LIVE price."""
        import redis.asyncio as aioredis
        from app.broker.paper_broker import place_paper_order
        from app.broker.tick_consumer import LTP_KEY
        from app.core.config import settings

        user = await _make_user(db, allow_offmarket_entry=False)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, entry="500.0000")
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = LTP_KEY.format(stock_id=stock.id)
        try:
            await r.set(key, "505.05", ex=600)
            order, _pos = await place_paper_order(db, user, signal, side="BUY", quantity=100)
            await db.commit()
            assert order.filled_price == Decimal("505.0500")  # live LTP (on tick grid)
        finally:
            await r.delete(key)
            await r.aclose()


# ── Paper record (30-day-clock view) ───────────────────────────────────────────

class TestPaperRecord:
    async def test_paper_record_aggregates_by_ist_day(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)

        def _d(day: int) -> datetime:
            return datetime(2026, 6, day, 12, 0, tzinfo=UTC)  # noon UTC → same IST date

        # Day 1: two trades net +1500 (profit). Day 2: -300 (loss).
        # Day 3: +500 (profit). Day 4: +200 (profit) → trailing streak = 2.
        await _closed_position(db, user, stock, signal, Decimal("1000"), closed_at=_d(1))
        await _closed_position(db, user, stock, signal, Decimal("500"), closed_at=_d(1))
        await _closed_position(db, user, stock, signal, Decimal("-300"), closed_at=_d(2))
        await _closed_position(db, user, stock, signal, Decimal("500"), closed_at=_d(3))
        await _closed_position(db, user, stock, signal, Decimal("200"), closed_at=_d(4))
        await db.commit()

        r = await client.get("/api/v1/trading/paper-record", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_days_traded"] == 4
        assert data["profitable_days"] == 3
        assert data["losing_days"] == 1
        assert data["current_streak"] == 2      # days 3 and 4
        assert data["best_streak"] == 2
        assert data["total_trades"] == 5
        assert Decimal(data["total_realized_pnl"]) == Decimal("1900")  # 1500-300+500+200
        assert data["start_date"] == "2026-06-01"
        assert data["last_date"] == "2026-06-04"
        # chronological + cumulative
        assert [d["date"] for d in data["days"]] == [
            "2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"
        ]
        assert Decimal(data["days"][0]["realized_pnl"]) == Decimal("1500")
        assert Decimal(data["days"][-1]["cumulative_pnl"]) == Decimal("1900")

    async def test_paper_record_empty(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/trading/paper-record", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_days_traded"] == 0
        assert data["days"] == []
        assert data["current_streak"] == 0
        assert data["start_date"] is None
