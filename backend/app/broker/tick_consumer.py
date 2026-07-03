"""Kite WebSocket tick consumer — Phase 7.

Architecture:
  KiteTicker (kiteconnect, threaded) ──on_ticks──► asyncio.Queue
                                                         │
                                          _process_ticks coroutine
                                                         │
                                   ┌─────────────────────┤
                           CandleAggregator       Redis PUBLISH
                                   │                    (ltp:{sid})
                           DB upsert candle         (candle:{sid}:{tf})
                           (on complete only)

The consumer is started as a background asyncio task by the FastAPI lifespan.
It self-reconnects on errors with exponential back-off.

Signal regeneration: when a candle closes, we fire a Celery task that runs the
confluence engine for that stock+timeframe (exactly the same path as the nightly
batch but on the live candle).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from kiteconnect import KiteTicker

from app.broker.candle_aggregator import TIMEFRAME_TABLE, AggregatorRegistry
from app.broker.kite_client import get_active_token
from app.core.config import settings

log = logging.getLogger(__name__)

# Redis channel prefixes
# ltp:{instrument_token}    → {"instrument_token": .., "stock_id": .., "ltp": .., "ts": ..}
# candle:{table}:{stock_id} → full candle JSON + is_complete flag
LTP_CHANNEL = "ltp:{instrument_token}"
CANDLE_CHANNEL = "candle:{table}:{stock_id}"

_registry = AggregatorRegistry()
# instrument_token → stock_id (populated during subscribe)
_token_to_stock: dict[int, int] = {}


class TickConsumer:
    """Manages Kite WebSocket lifecycle for a single access_token."""

    def __init__(
        self,
        access_token: str,
        token_stock_map: dict[int, int],
        redis_url: str,
    ) -> None:
        self._access_token = access_token
        self._token_stock_map = token_stock_map
        self._redis_url = redis_url
        self._queue: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue(maxsize=10_000)
        self._ticker: KiteTicker | None = None
        self._running = False

    # ── Public interface ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the KiteTicker in a thread and process ticks in the event loop."""
        self._running = True
        self._ticker = KiteTicker(
            api_key=settings.kite_api_key,
            access_token=self._access_token,
            reconnect=True,
            reconnect_max_tries=50,
        )
        self._ticker.on_ticks = self._on_ticks_thread
        self._ticker.on_connect = self._on_connect
        self._ticker.on_error = self._on_error
        self._ticker.on_close = self._on_close

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._ticker.connect, True)  # non-blocking connect
        await self._process_loop()

    async def stop(self) -> None:
        self._running = False
        if self._ticker:
            self._ticker.stop()

    # ── KiteTicker callbacks (run on ticker's thread) ─────────────────────────

    def _on_ticks_thread(self, ws: Any, ticks: list[dict[str, Any]]) -> None:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self._queue.put_nowait, ticks)

    def _on_connect(self, ws: Any, response: Any) -> None:
        tokens = list(self._token_stock_map.keys())
        log.info("KiteTicker connected; subscribing to %d instruments", len(tokens))
        if tokens and self._ticker:
            self._ticker.subscribe(tokens)
            self._ticker.set_mode(KiteTicker.MODE_FULL, tokens)

    def _on_error(self, ws: Any, code: Any, reason: Any) -> None:
        log.error("KiteTicker error code=%s reason=%s", code, reason)

    def _on_close(self, ws: Any, code: Any, reason: Any) -> None:
        log.warning("KiteTicker closed code=%s reason=%s", code, reason)

    # ── Async processing loop ────────────────────────────────────────────────

    async def _process_loop(self) -> None:
        import redis.asyncio as aioredis

        r = aioredis.from_url(self._redis_url, decode_responses=True)
        from app.db.session import AsyncSessionFactory

        async with AsyncSessionFactory() as db:
            while self._running:
                try:
                    ticks: list[dict[str, Any]] = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except TimeoutError:
                    continue

                for tick in ticks:
                    await self._handle_tick(tick, r, db)

    async def _handle_tick(
        self,
        tick: dict[str, Any],
        redis: Any,
        db: Any,
    ) -> None:
        instrument_token = tick.get("instrument_token")
        if instrument_token is None:
            return

        stock_id = self._token_stock_map.get(instrument_token)
        if stock_id is None:
            return

        ltp = tick.get("last_price") or tick.get("last_traded_price")
        if ltp is None:
            return

        # Publish LTP update
        ltp_payload = json.dumps(
            {
                "instrument_token": instrument_token,
                "stock_id": stock_id,
                "ltp": float(ltp),
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        await redis.publish(LTP_CHANNEL.format(instrument_token=instrument_token), ltp_payload)

        # Aggregate into candles
        agg = _registry.get_or_create(stock_id)
        events = agg.on_tick(tick)

        for event in events:
            candle = event.candle
            table = TIMEFRAME_TABLE[candle.timeframe]

            # Publish candle update (live or closed)
            candle_payload = json.dumps(
                {
                    "stock_id": stock_id,
                    "timeframe": candle.timeframe,
                    "time": candle.period_start.isoformat(),
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": candle.volume,
                    "is_complete": candle.is_complete,
                }
            )
            await redis.publish(
                CANDLE_CHANNEL.format(table=table, stock_id=stock_id),
                candle_payload,
            )

            # Persist to DB: always upsert (live updates in-place, closed marks complete)
            if event.is_new or event.is_closed:
                await _upsert_candle(db, table, stock_id, candle)

            if event.is_closed:
                log.debug(
                    "Candle closed: stock_id=%d tf=%s time=%s",
                    stock_id, candle.timeframe, candle.period_start,
                )
                _maybe_trigger_signal(stock_id, candle.timeframe)

        # Flush after each batch of events
        try:
            await db.flush()
        except Exception:
            log.exception("DB flush error in tick handler")
            await db.rollback()


async def _upsert_candle(db: Any, table: str, stock_id: int, candle: Any) -> None:
    from sqlalchemy import text

    await db.execute(
        text(
            f"INSERT INTO {table} (time, stock_id, open, high, low, close, volume, is_complete)"  # noqa: S608
            " VALUES (:time, :sid, :open, :high, :low, :close, :volume, :complete)"
            " ON CONFLICT (time, stock_id) DO UPDATE SET"
            "   high        = GREATEST(EXCLUDED.high, {table}.high),"
            "   low         = LEAST(EXCLUDED.low, {table}.low),"
            "   close       = EXCLUDED.close,"
            "   volume      = EXCLUDED.volume,"
            "   is_complete = EXCLUDED.is_complete"
        ).format(table=table).bindparams(
            time=candle.period_start,
            sid=stock_id,
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
            volume=candle.volume,
            complete=candle.is_complete,
        )
    )


def _maybe_trigger_signal(stock_id: int, timeframe: str) -> None:
    """Fire a Celery task to regenerate signals on candle close (best-effort)."""
    try:
        from app.celery_app import celery_app
        celery_app.send_task(
            "app.tasks.signal_tasks.live_signal_generation",
            kwargs={"stock_id": stock_id, "timeframe": timeframe},
        )
    except Exception:
        log.debug("Could not fire live signal task (Celery not running?)")


# ── Module-level consumer instance (singleton per process) ───────────────────

_consumer: TickConsumer | None = None


async def start_consumer(user_id: int) -> bool:
    """Start the global tick consumer for the given user's active token.

    Called from FastAPI lifespan.  Returns True if consumer started.
    """
    global _consumer

    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        token = await get_active_token(db, user_id)
        if token is None:
            log.info("No active Kite token for user_id=%d; tick consumer not started", user_id)
            return False

        # Build instrument_token → stock_id mapping
        token_stock_map = await _build_token_stock_map(db, token.access_token)
        if not token_stock_map:
            log.warning("No instrument tokens mapped; tick consumer not started")
            return False

    _consumer = TickConsumer(
        access_token=token.access_token,
        token_stock_map=token_stock_map,
        redis_url=settings.redis_url,
    )
    asyncio.create_task(_consumer.start(), name="tick_consumer")
    log.info("Tick consumer started with %d instruments", len(token_stock_map))
    return True


async def stop_consumer() -> None:
    global _consumer
    if _consumer:
        await _consumer.stop()
        _consumer = None


async def _build_token_stock_map(db: Any, access_token: str) -> dict[int, int]:
    """Return {instrument_token: stock_id} for all active NSE EQ stocks."""
    from sqlalchemy import text


    # Join kite_instruments with stocks on tradingsymbol + exchange
    result = await db.execute(
        text(
            "SELECT ki.instrument_token, s.id"
            " FROM kite_instruments ki"
            " JOIN stocks s ON s.symbol = ki.tradingsymbol AND s.exchange = ki.exchange"
            " WHERE s.is_active = true AND ki.instrument_type = 'EQ'"
        )
    )
    rows = result.fetchall()
    return {row[0]: row[1] for row in rows}


def get_consumer() -> TickConsumer | None:
    return _consumer
