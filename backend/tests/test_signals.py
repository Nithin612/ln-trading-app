"""Integration tests for signal API endpoints."""

from datetime import UTC, datetime, timedelta

from app.models.signal import Signal
from app.models.stock import Stock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers


async def create_admin(db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", password="adminpass123", role="admin")


async def get_token(client: AsyncClient, email: str, password: str) -> str:
    headers = await get_auth_headers(client, email=email, password=password)
    return headers["Authorization"].removeprefix("Bearer ")


async def _make_stock(db: AsyncSession, symbol: str = "TATAMOTORS") -> Stock:
    stock = Stock(
        symbol=symbol,
        exchange="NSE",
        company_name="Tata Motors Limited",
        is_active=True,
        is_nifty50=True,
    )
    db.add(stock)
    await db.flush()
    return stock


async def _make_signal(
    db: AsyncSession,
    stock_id: int,
    direction: str = "BUY",
    confidence_pct: int = 80,
    classification: str = "swing",
    status: str = "active",
) -> Signal:
    now = datetime.now(tz=UTC)
    signal = Signal(
        stock_id=stock_id,
        direction=direction,
        classification=classification,
        timeframe="1d",
        entry_price="490.0000",
        stop_loss="482.0000",
        take_profit="506.0000",
        suggested_qty=250,
        confidence_pct=confidence_pct,
        factor_scores={"DOW_TREND": {"weight": 20, "score": 0.7, "explanation": "uptrend"}},
        triggering_patterns=["BULLISH_ENGULFING"],
        triggering_indicators=["RSI_DIVERGENCE"],
        headline="BUY TATAMOTORS — 80% confidence",
        status=status,
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(signal)
    await db.flush()
    return signal


class TestSignalsActive:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/signals/active")
        assert r.status_code == 401

    async def test_empty_list(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        r = await client.get(
            "/api/v1/signals/active",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["signals"] == []

    async def test_returns_active_signals(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["signals"][0]["id"] == sig.id
        assert data["signals"][0]["direction"] == "BUY"
        assert data["signals"][0]["confidence_pct"] == 80

    async def test_expired_signals_excluded(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)

        # Expired signal
        now = datetime.now(tz=UTC)
        expired = Signal(
            stock_id=stock.id,
            direction="BUY",
            classification="swing",
            timeframe="1d",
            entry_price="490.0000",
            stop_loss="482.0000",
            take_profit="506.0000",
            suggested_qty=250,
            confidence_pct=80,
            factor_scores={},
            headline="expired signal",
            status="active",
            validity_until=now - timedelta(hours=1),  # already expired
            created_at=now - timedelta(days=6),
        )
        db.add(expired)
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_filter_by_direction(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        await _make_signal(db, stock.id, direction="BUY")
        await _make_signal(db, stock.id, direction="SELL")
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?direction=BUY",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert all(s["direction"] == "BUY" for s in data["signals"])

    async def test_filter_by_classification(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        await _make_signal(db, stock.id, classification="swing")
        await _make_signal(db, stock.id, classification="scalp")
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?classification=swing",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert all(s["classification"] == "swing" for s in data["signals"])

    async def test_filter_by_min_confidence(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        await _make_signal(db, stock.id, confidence_pct=75)
        await _make_signal(db, stock.id, confidence_pct=85)
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?min_confidence=80",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert all(s["confidence_pct"] >= 80 for s in data["signals"])

    async def test_sorted_by_confidence_desc(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        await _make_signal(db, stock.id, confidence_pct=75)
        await _make_signal(db, stock.id, confidence_pct=90)
        await _make_signal(db, stock.id, confidence_pct=82)
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?min_confidence=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        confidences = [s["confidence_pct"] for s in r.json()["signals"]]
        assert confidences == sorted(confidences, reverse=True)


class TestSignalDetail:
    async def test_get_signal_by_id(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        stock = await _make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.get(
            f"/api/v1/signals/{sig.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == sig.id
        assert "factor_scores" in data
        assert data["symbol"] == "TATAMOTORS"

    async def test_not_found(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_admin(db)
        token = await get_token(client, "admin@example.com", "adminpass123")
        r = await client.get(
            "/api/v1/signals/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
