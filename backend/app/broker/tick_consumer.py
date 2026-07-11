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
# CONTRACT: subscribe with exact SUBSCRIBE — the live worker gates
# publishes on PUBSUB CHANNELS, which cannot see patterns. A PSUBSCRIBE
# still works (the worker detects it via PUBSUB NUMPAT and falls back to
# publish-everything until the pattern subscriber disconnects) but that
# defeats the fan-out gating for everyone — don't.
LTP_CHANNEL = "ltp:{instrument_token}"
CANDLE_CHANNEL = "candle:{table}:{stock_id}"

# Redis KEY holding the latest price per stock (plain Decimal-parseable string).
# paper_broker.get_current_price reads this exact key — import it from here,
# never retype the pattern.
LTP_KEY = "ltp:{stock_id}"
LTP_KEY_TTL_SECONDS = 600  # stale after 10 min without ticks

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
        # Captured in start(); KiteTicker callbacks run on the ticker's own
        # thread where asyncio.get_event_loop() raises on Python 3.12.
        self._loop: asyncio.AbstractEventLoop | None = None
        # Candle-close signal triggers held until the batch COMMITs — the
        # Celery task reads candles from its own session.
        self._pending_triggers: list[tuple[int, str]] = []

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

        self._loop = asyncio.get_running_loop()
        try:
            # threaded=True returns immediately (Twisted reactor on its own
            # thread) — a synchronous raise here (bad API key) must surface,
            # not vanish into a discarded executor future.
            self._ticker.connect(threaded=True)
        except Exception:
            log.exception("KiteTicker connect failed; consumer not started")
            self._running = False
            return
        await self._process_loop()

    async def stop(self) -> None:
        self._running = False
        if self._ticker:
            self._ticker.stop()

    # ── KiteTicker callbacks (run on ticker's thread) ─────────────────────────

    def _on_ticks_thread(self, ws: Any, ticks: list[dict[str, Any]]) -> None:
        # Runs on the KiteTicker thread: never touch asyncio state directly here.
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._enqueue, ticks)

    def _enqueue(self, ticks: list[dict[str, Any]]) -> None:
        """Runs on the event-loop thread. Drops the oldest batch when full —
        losing a stale LTP batch beats crashing the callback chain."""
        try:
            self._queue.put_nowait(ticks)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(ticks)
            log.warning("Tick queue full; dropped oldest batch")

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

    def _make_redis(self) -> Any:
        """Redis client factory — a seam so tests can inject a fake."""
        import redis.asyncio as aioredis

        return aioredis.from_url(self._redis_url, decode_responses=True)

    async def _process_loop(self) -> None:
        import contextlib

        r = self._make_redis()
        from app.db.session import AsyncSessionFactory

        try:
            async with AsyncSessionFactory() as db:
                while self._running:
                    try:
                        ticks: list[dict[str, Any]] = await asyncio.wait_for(
                            self._queue.get(), timeout=1.0
                        )
                    except TimeoutError:
                        continue

                    # One bad batch (Redis blip, DB hiccup) must NEVER kill the
                    # loop — that silently ends live data for the whole day.
                    try:
                        await self._process_batch(ticks, r, db)
                    except Exception:
                        log.exception("Tick batch failed; dropping batch, loop continues")
                        with contextlib.suppress(Exception):
                            await db.rollback()
                        self._log_dropped_triggers()
                        self._pending_triggers.clear()
        finally:
            with contextlib.suppress(Exception):
                await r.aclose()

    async def _process_batch(self, ticks: list[dict[str, Any]], r: Any, db: Any) -> None:
        wrote = False
        for tick in ticks:
            wrote = await self._handle_tick(tick, r, db) or wrote

        # Commit once per Kite batch (~1/sec). flush() alone left the
        # transaction open all day and candles invisible to readers.
        if wrote:
            try:
                await db.commit()
            except Exception:
                log.exception("DB commit error in tick batch")
                await db.rollback()
                self._log_dropped_triggers()
                self._pending_triggers.clear()
                return

        # Fire signal regeneration only after the candles are visible.
        # kombu publish is a blocking call — keep it off the event loop.
        triggers, self._pending_triggers = self._pending_triggers, []
        if triggers:
            await asyncio.to_thread(_fire_signal_triggers, triggers)

    def _log_dropped_triggers(self) -> None:
        """Breadcrumb for manual backfill: closed candles whose upsert batch
        failed are not retried (the aggregator has moved on)."""
        for stock_id, timeframe in self._pending_triggers:
            log.error(
                "Dropped candle-close trigger after failed batch: stock_id=%d tf=%s",
                stock_id, timeframe,
            )

    async def _handle_tick(
        self,
        tick: dict[str, Any],
        redis: Any,
        db: Any,
    ) -> bool:
        """Process one tick. Returns True if it wrote to the DB session."""
        instrument_token = tick.get("instrument_token")
        if instrument_token is None:
            return False

        stock_id = self._token_stock_map.get(instrument_token)
        if stock_id is None:
            return False

        ltp = tick.get("last_price") or tick.get("last_traded_price")
        if ltp is None:
            return False

        # Latest-price KEY (read by paper_broker for fills and SL/TP checks) …
        await redis.set(
            LTP_KEY.format(stock_id=stock_id), str(ltp), ex=LTP_KEY_TTL_SECONDS
        )
        # … and pub/sub CHANNEL for the live WebSocket fan-out.
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

        wrote = False
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
                wrote = True

            if event.is_closed:
                log.debug(
                    "Candle closed: stock_id=%d tf=%s time=%s",
                    stock_id, candle.timeframe, candle.period_start,
                )
                self._pending_triggers.append((stock_id, candle.timeframe))

        return wrote


async def _upsert_candle(db: Any, table: str, stock_id: int, candle: Any) -> None:
    from sqlalchemy import text

    if table not in TIMEFRAME_TABLE.values():  # defence-in-depth for the f-string SQL
        raise ValueError(f"Unknown candle table: {table}")

    # NOTE: former code called .format() on the TextClause (AttributeError —
    # killed the loop on the first candle) and bound prices as float.
    await db.execute(
        text(
            f"INSERT INTO {table} (time, stock_id, open, high, low, close, volume, is_complete)"  # noqa: S608
            " VALUES (:time, :sid, :open, :high, :low, :close, :volume, :complete)"
            " ON CONFLICT (time, stock_id) DO UPDATE SET"
            f"   high        = GREATEST(EXCLUDED.high, {table}.high),"
            f"   low         = LEAST(EXCLUDED.low, {table}.low),"
            "   close       = EXCLUDED.close,"
            "   volume      = EXCLUDED.volume,"
            "   is_complete = EXCLUDED.is_complete"
        ).bindparams(
            time=candle.period_start,
            sid=stock_id,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            complete=candle.is_complete,
        )
    )


def _fire_signal_triggers(triggers: list[tuple[int, str]]) -> None:
    """Fire Celery tasks for a batch of candle closes.

    Runs on a worker thread (kombu publish blocks); called via
    asyncio.to_thread so aligned closes (10:00 → every TF for every stock)
    can't stall the tick loop.
    """
    for stock_id, timeframe in triggers:
        _maybe_trigger_signal(stock_id, timeframe)


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
_consumer_task: asyncio.Task[None] | None = None


def _on_consumer_done(task: asyncio.Task[None]) -> None:
    """A dead consumer must be LOUD — silence here once cost a full trading day."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        log.critical("Tick consumer task DIED: %r", exc, exc_info=exc)


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

    global _consumer_task
    _consumer = TickConsumer(
        access_token=token.access_token,
        token_stock_map=token_stock_map,
        redis_url=settings.redis_url,
    )
    _consumer_task = asyncio.create_task(_consumer.start(), name="tick_consumer")
    _consumer_task.add_done_callback(_on_consumer_done)
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
