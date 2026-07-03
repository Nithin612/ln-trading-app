"""Regression tests for the four Phase 0 tick-consumer defects.

The live pipeline had never run end-to-end:
  1. asyncio.get_event_loop() on the KiteTicker thread → RuntimeError (3.12)
  2. .format() called on a TextClause → AttributeError on first candle
  3. flush() without commit → candles invisible to other sessions
  4. LTP published to a channel but never SET as a key → paper broker
     always fell back to stale EOD closes
"""

import asyncio
import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from app.broker.candle_aggregator import Candle
from app.broker.tick_consumer import (
    LTP_KEY,
    LTP_KEY_TTL_SECONDS,
    TickConsumer,
    _upsert_candle,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _make_consumer() -> TickConsumer:
    return TickConsumer(
        access_token="test-token",
        token_stock_map={123: 1},
        redis_url="redis://localhost:6379/9",
    )


class _RedisSpy:
    """Records set/publish calls without a real Redis."""

    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.publish_calls: list[tuple[str, str]] = []

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.set_calls.append((key, value, ex))

    async def publish(self, channel: str, payload: str) -> None:
        self.publish_calls.append((channel, payload))


class TestCrossThreadDelivery:
    async def test_on_ticks_from_foreign_thread_reaches_queue(self) -> None:
        """The KiteTicker callback runs on its own thread; ticks must still land."""
        consumer = _make_consumer()
        consumer._loop = asyncio.get_running_loop()
        ticks = [{"instrument_token": 123, "last_price": 101.5}]

        t = threading.Thread(target=consumer._on_ticks_thread, args=(None, ticks))
        t.start()
        t.join(timeout=2)

        received = await asyncio.wait_for(consumer._queue.get(), timeout=2)
        assert received == ticks

    async def test_callback_before_start_is_safe(self) -> None:
        """No loop captured yet → callback must not raise on the ticker thread."""
        consumer = _make_consumer()
        errors: list[BaseException] = []

        def run() -> None:
            try:
                consumer._on_ticks_thread(None, [{"instrument_token": 123}])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=2)
        assert errors == []

    async def test_enqueue_drops_oldest_when_full(self) -> None:
        consumer = _make_consumer()
        consumer._queue = asyncio.Queue(maxsize=2)
        consumer._enqueue([{"batch": 1}])
        consumer._enqueue([{"batch": 2}])
        consumer._enqueue([{"batch": 3}])  # full → drops batch 1

        assert consumer._queue.qsize() == 2
        assert await consumer._queue.get() == [{"batch": 2}]
        assert await consumer._queue.get() == [{"batch": 3}]


class TestUpsertCandle:
    async def test_insert_then_update_merges_high_low(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="TICKCO")
        await db.commit()
        period = datetime(2026, 7, 3, 4, 0, tzinfo=UTC)

        first = Candle(
            stock_id=stock.id, timeframe="5m", period_start=period,
            open=Decimal("100.00"), high=Decimal("101.00"),
            low=Decimal("99.50"), close=Decimal("100.50"), volume=1000,
        )
        await _upsert_candle(db, "ohlcv_5m", stock.id, first)
        await db.commit()

        second = Candle(
            stock_id=stock.id, timeframe="5m", period_start=period,
            open=Decimal("100.00"), high=Decimal("102.00"),
            low=Decimal("99.00"), close=Decimal("101.75"), volume=2500,
            is_complete=True,
        )
        await _upsert_candle(db, "ohlcv_5m", stock.id, second)
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT open, high, low, close, volume, is_complete"
                    " FROM ohlcv_5m WHERE stock_id = :sid AND time = :t"
                ).bindparams(sid=stock.id, t=period)
            )
        ).one()
        assert row.open == Decimal("100.0000")
        assert row.high == Decimal("102.0000")   # GREATEST kept the new high
        assert row.low == Decimal("99.0000")     # LEAST kept the new low
        assert row.close == Decimal("101.7500")
        assert row.volume == 2500
        assert row.is_complete is True

    async def test_unknown_table_rejected(self, db: AsyncSession) -> None:
        candle = Candle(
            stock_id=1, timeframe="5m",
            period_start=datetime(2026, 7, 3, 4, 0, tzinfo=UTC),
            open=Decimal("1"), high=Decimal("1"),
            low=Decimal("1"), close=Decimal("1"), volume=1,
        )
        with pytest.raises(ValueError, match="Unknown candle table"):
            await _upsert_candle(db, "users; DROP TABLE users", 1, candle)


class TestLtpKey:
    async def test_handle_tick_sets_key_and_publishes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.broker import tick_consumer as tc

        class _NoopAgg:
            def on_tick(self, tick: dict[str, Any]) -> list[Any]:
                return []

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        consumer = _make_consumer()
        spy = _RedisSpy()

        wrote = await consumer._handle_tick(
            {"instrument_token": 123, "last_price": 2468.9}, spy, db=None
        )

        assert wrote is False  # no candle events → no DB write
        assert spy.set_calls == [
            (LTP_KEY.format(stock_id=1), "2468.9", LTP_KEY_TTL_SECONDS)
        ]
        assert len(spy.publish_calls) == 1
        assert spy.publish_calls[0][0] == "ltp:123"

    async def test_paper_broker_reads_the_same_key(self, db: AsyncSession) -> None:
        """End-to-end contract: SET by consumer key-pattern, read by paper broker."""
        import redis.asyncio as aioredis
        from app.broker.paper_broker import get_current_price
        from app.core.config import settings

        stock = await make_stock(db, symbol="LTPCO")
        await db.commit()

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = LTP_KEY.format(stock_id=stock.id)
        try:
            await r.set(key, "1234.55", ex=60)
            price = await get_current_price(db, stock.id)
            assert price == Decimal("1234.55")  # Redis, not EOD fallback
        finally:
            await r.delete(key)
            await r.aclose()


class TestLoopSurvival:
    async def test_bad_batch_does_not_kill_the_loop(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient Redis error in one batch must not end live data for
        the day: the loop drops the batch, logs, and processes the next one."""
        from app.broker import tick_consumer as tc

        class _NoopAgg:
            def on_tick(self, tick: dict[str, Any]) -> list[Any]:
                return []

        class _FlakyRedis(_RedisSpy):
            def __init__(self) -> None:
                super().__init__()
                self.calls = 0

            async def set(self, key: str, value: str, ex: int | None = None) -> None:
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("transient redis blip")
                await super().set(key, value, ex=ex)

            async def aclose(self) -> None:
                pass

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        consumer = _make_consumer()
        flaky = _FlakyRedis()
        monkeypatch.setattr(consumer, "_make_redis", lambda: flaky)
        consumer._running = True

        task = asyncio.create_task(consumer._process_loop())
        try:
            consumer._queue.put_nowait([{"instrument_token": 123, "last_price": 100.0}])
            consumer._queue.put_nowait([{"instrument_token": 123, "last_price": 101.0}])
            # Wait for the second (good) batch to be processed
            for _ in range(50):
                if flaky.set_calls:
                    break
                await asyncio.sleep(0.05)
            assert not task.done(), "loop died on a transient error"
            assert flaky.set_calls, "second batch was never processed"
            assert flaky.set_calls[0][1] == "101.0"
        finally:
            consumer._running = False
            await asyncio.wait_for(task, timeout=5)
