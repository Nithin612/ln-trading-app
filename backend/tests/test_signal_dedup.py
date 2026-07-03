"""Regression tests for signal idempotency (Phase 0 triage).

Candle-close regeneration used to insert a near-identical signal on every
period while the previous one was still active — nothing deduplicated.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.market_data import Ohlcv5m
from app.models.signal import Signal
from app.services.signal_service import (
    _has_active_signal,
    run_live_signal_generation,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _make_signal_row(stock_id: int, **overrides: object) -> Signal:
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = {
        "stock_id": stock_id,
        "direction": "BUY",
        "classification": "scalp",
        "timeframe": "5m",
        "entry_price": Decimal("100.0000"),
        "stop_loss": Decimal("99.7000"),
        "take_profit": Decimal("100.4500"),
        "suggested_qty": 100,
        "confidence_pct": 75,
        "factor_scores": {},
        "headline": "test signal",
        "status": "active",
        "validity_until": now + timedelta(minutes=30),
        "created_at": now,
    }
    defaults.update(overrides)
    return Signal(**defaults)


class TestHasActiveSignal:
    async def test_active_unexpired_signal_found(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="DEDUP1")
        db.add(_make_signal_row(stock.id))
        await db.commit()
        assert await _has_active_signal(db, stock.id, "5m", "BUY") is True

    async def test_expired_signal_ignored(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="DEDUP2")
        db.add(
            _make_signal_row(
                stock.id,
                validity_until=datetime.now(tz=UTC) - timedelta(minutes=1),
            )
        )
        await db.commit()
        assert await _has_active_signal(db, stock.id, "5m", "BUY") is False

    async def test_other_direction_and_timeframe_ignored(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="DEDUP3")
        db.add(_make_signal_row(stock.id))
        await db.commit()
        assert await _has_active_signal(db, stock.id, "5m", "SELL") is False
        assert await _has_active_signal(db, stock.id, "15m", "BUY") is False

    async def test_resolved_status_ignored(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="DEDUP4")
        db.add(_make_signal_row(stock.id, status="hit_tp"))
        await db.commit()
        assert await _has_active_signal(db, stock.id, "5m", "BUY") is False


class _FakeScore:
    direction = "BUY"
    confidence_pct = 78
    factors: list[object] = []
    is_multibagger = False
    triggering_patterns = ["bullish_engulfing"]
    triggering_indicators = ["rsi"]


async def _seed_5m_candles(db: AsyncSession, stock_id: int, n: int = 60) -> None:
    start = datetime(2026, 7, 3, 4, 0, tzinfo=UTC)
    for i in range(n):
        db.add(
            Ohlcv5m(
                time=start + timedelta(minutes=5 * i),
                stock_id=stock_id,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99.5"),
                close=Decimal("100.5"),
                volume=1000,
                is_complete=True,
            )
        )
    await db.commit()


class TestLiveGenerationIdempotency:
    async def test_second_run_does_not_duplicate(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.signal_service as svc

        stock = await make_stock(db, symbol="DEDUP5")
        await db.commit()
        await _seed_5m_candles(db, stock.id)
        monkeypatch.setattr(svc, "score_signal", lambda *a, **kw: _FakeScore())
        monkeypatch.setattr(svc, "build_headline", lambda *a, **kw: "fake headline")

        first = await run_live_signal_generation(
            db, stock.id, "5m", Decimal("500000"), Decimal("2")
        )
        second = await run_live_signal_generation(
            db, stock.id, "5m", Decimal("500000"), Decimal("2")
        )

        assert first == 1
        assert second == 0  # dedup guard skipped the insert
        count = (
            await db.execute(
                select(func.count()).select_from(Signal).where(Signal.stock_id == stock.id)
            )
        ).scalar_one()
        assert count == 1
