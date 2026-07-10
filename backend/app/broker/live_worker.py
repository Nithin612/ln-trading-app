"""Dedicated live-worker process (Phase 3, slice 3.3).

Replaces the v1 in-app asyncio tick consumer with the plan §2 topology —
no asyncio anywhere near the hot path:

    KiteTicker thread ──► bounded queue.Queue ──► consumer THREAD
        (drop-oldest for tick batches;            │ ONE tradecore.LiveBook
         time pulses share the queue so           │ call per batch
         tick/pulse ordering is serialized        ▼
         and replayable)                    sync redis-py:
                                            SET ltp:{stock_id} + PUBLISH
                                            (LTP + candle channels)
        committed candles ──► writer queue (BLOCKING put — a candle close
        is never dropped) ──► writer THREAD (its own event loop + its own
        engine, created in-thread: the Celery pool-×-loop lesson) ──►
        Postgres upsert ──► Celery signal trigger AFTER commit.

Daily lifecycle (design: restart, don't reconnect): the Kite token dies
~6:00 AM IST; the WS closing is a NORMAL event — the process exits and
the supervisor (systemd unit / `make live-worker` loop) restarts it; a
restart without a valid token exits code 4 and waits for the login
ritual. Run as `python -m app.broker.live_worker` (add --gap-fill to
REST-backfill gaps for the subscribed instruments before connecting).

Record hook (slice-3.4 seed): when settings.live_record_path is set, the
consumer thread appends every tick batch AND every time pulse as JSONL
before processing — the exact input stream replay needs, in the exact
order the engine saw it.

The engine session guard (09:15–15:30 IST, per the 3.1 canon) makes
pre-open/post-close ticks harmless; holidays simply deliver no ticks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import queue
import threading
import time as time_mod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, TextIO
from zoneinfo import ZoneInfo

from app.broker.candle_aggregator import TIMEFRAME_TABLE
from app.broker.live_levels import LevelDict, LevelDirectory, LevelMeta, build_directory
from app.broker.tick_consumer import (
    CANDLE_CHANNEL,
    LTP_CHANNEL,
    LTP_KEY,
    LTP_KEY_TTL_SECONDS,
    _build_token_stock_map,
    _maybe_trigger_signal,
)
from app.core.config import settings

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

# Timeframes the LiveBook mints, and their label/table mapping.
TF_MINUTES: list[int] = [1, 5, 15, 60]
TF_LABEL: dict[int, str] = {1: "1m", 5: "5m", 15: "15m", 60: "1h"}

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)

_QUEUE_MAX = 10_000

# Consumer-queue items: (kind, payload, monotonic-enqueue-stamp-or-None).
QueueItem = tuple[str, Any, float | None]
_PULSE_INTERVAL_S = 1.0

# Exit codes for the supervisor: 0 clean stop · 3 WS died mid-session ·
# 4 no usable token (wait for the login ritual).
EXIT_WS_DIED = 3
EXIT_NO_TOKEN = 4


def session_bounds_ist(day: date) -> tuple[int, int]:
    """(open_ts, close_ts) epoch seconds for a standard NSE session."""
    open_dt = datetime.combine(day, SESSION_OPEN, tzinfo=_IST)
    close_dt = datetime.combine(day, SESSION_CLOSE, tzinfo=_IST)
    return int(open_dt.timestamp()), int(close_dt.timestamp())


def tick_to_ffi(
    tick: dict[str, Any], token_map: dict[int, int]
) -> tuple[int, int, str, int | None, int] | None:
    """Kite tick dict → LiveBook FFI tuple (stock_id, ts, price, dayvol, qty).

    kiteconnect delivers exchange_timestamp as a NAIVE datetime in the
    HOST's local zone — astimezone(UTC) converts correctly whatever the
    host zone is (`.replace` would mislabel by +5:30 on an IST machine;
    same lesson as the v1 aggregator). Unusable ticks return None.
    """
    stock_id = token_map.get(tick.get("instrument_token", -1))
    if stock_id is None:
        return None
    ltp = tick.get("last_price") or tick.get("last_traded_price")
    if not ltp:
        return None
    ts_raw = tick.get("exchange_timestamp") or tick.get("last_trade_time")
    if isinstance(ts_raw, datetime):
        ts = int(ts_raw.astimezone(UTC).timestamp())
    else:
        ts = int(time_mod.time())
    day_vol_raw = tick.get("volume_traded")
    day_volume = int(day_vol_raw) if day_vol_raw is not None else None
    qty = int(tick.get("last_traded_quantity") or tick.get("last_quantity", 0) or 0)
    return stock_id, ts, str(ltp), day_volume, qty


def _money(raw: int) -> Decimal:
    """Exact i64·1e-4 → Decimal (never through float)."""
    return Decimal(raw) / Decimal(10_000)


class LatencyHistogram:
    """Fixed-bucket ms histogram — no per-observation allocation, exact
    counts; percentiles are bucket upper bounds (conservative)."""

    BOUNDS_MS = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)

    def __init__(self) -> None:
        self.counts = [0] * (len(self.BOUNDS_MS) + 1)
        self.n = 0
        self.max_ms = 0.0

    def observe(self, ms: float) -> None:
        self.n += 1
        self.max_ms = max(self.max_ms, ms)
        for i, bound in enumerate(self.BOUNDS_MS):
            if ms <= bound:
                self.counts[i] += 1
                return
        self.counts[-1] += 1

    def quantile_bound(self, q: float) -> float:
        """Smallest bucket bound covering quantile q (inf bucket → max)."""
        if self.n == 0:
            return 0.0
        target = q * self.n
        seen = 0
        for i, bound in enumerate(self.BOUNDS_MS):
            seen += self.counts[i]
            if seen >= target:
                return bound
        return self.max_ms

    def summary(self) -> dict[str, float | int]:
        return {
            "n": self.n,
            "p50_ms": self.quantile_bound(0.50),
            "p99_ms": self.quantile_bound(0.99),
            "max_ms": round(self.max_ms, 3),
        }


@dataclass
class WorkerState:
    """Everything the consumer thread needs — built once at startup,
    driven synchronously (threads are thin wrappers; tests call
    process_item directly)."""

    book: Any  # tradecore.LiveBook
    token_map: dict[int, int]
    redis: Any  # sync redis-py client (or a test spy)
    writer_q: queue.Queue[dict[str, Any] | None]
    recorder: TextIO | None = None
    # Snapshot-echo guard (mid-session restart): Kite's subscribe snapshot
    # replays each instrument's LAST tick, whose timestamp can predate the
    # restart — a fresh book would re-mint an already-persisted bucket and
    # the upsert would clobber it. Ticks older than this are skipped.
    min_tick_ts: int = 0
    writer_alive: Any = None  # () -> bool; None = assume alive (tests)
    stop_event: Any = None  # threading.Event for fail-loud escalation
    stats: dict[str, int] = field(
        default_factory=lambda: {
            "ticks": 0, "pulses": 0, "committed": 0, "skipped": 0, "stale": 0,
            "levels": 0, "triggers": 0,
        }
    )
    latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    # Session day (ISO) stamped on every alert; set once at startup.
    session_day: str = ""
    # Host registry for alert enrichment: {stock_id: {level_id: meta}} —
    # owned by the consumer thread (updated via "levels" queue items).
    level_meta: dict[int, LevelMeta] = field(default_factory=dict)
    # Consumer-thread ack callback(sid, levels) — fires ONLY after the
    # engine accepted a set_levels; the refresher re-sends anything
    # unacked (eviction- and rejection-proof). None in tests.
    on_levels_applied: Any = None
    _stock_to_token: dict[int, int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._stock_to_token = {v: k for k, v in self.token_map.items()}
        if self.writer_alive is None:
            self.writer_alive = lambda: True

    def process_item(self, item: tuple[str, Any] | QueueItem) -> None:
        kind, payload = item[0], item[1]
        stamp = item[2] if len(item) > 2 else None
        if kind == "pulse":
            self.stats["pulses"] += 1
            events = self.book.on_time(payload)
            self._record({"k": "p", "ts": payload})
            self._enqueue_committed(events)
            try:
                self._publish_events(events)
            except Exception:
                log.exception("redis publish failed; continuing (at-most-once layer)")
            return
        if kind == "levels":
            self._apply_levels(payload)
            return
        batch = self._ffi_batch(payload)
        if not batch:
            return
        self.stats["ticks"] += len(batch)
        # Engine FIRST, durable writer queue SECOND, lossy redis LAST (a
        # redis blip must never starve the engine or drop a committed
        # candle). Recording happens AFTER the engine accepts the batch —
        # a raising batch is neither consumed nor recorded (symmetric with
        # replay), and a recorder failure can never abort processing
        # (bug-hunter HIGH, 2026-07-10).
        events = self.book.on_ticks(batch)
        for sid, ts, price, dv, qty in batch:
            self._record({"k": "t", "sid": sid, "ts": ts, "p": price, "dv": dv, "q": qty})
        self._enqueue_committed(events)
        self._publish_alerts(events)
        try:
            self._publish_ltp(batch)
            self._publish_events(events)
        except Exception:
            log.exception("redis publish failed; continuing (at-most-once layer)")
        if stamp is not None:
            # tick→publish latency (WS callback enqueue → redis pipeline
            # done) — the p99 < 10 ms phase target, measured per batch.
            self.latency.observe((time_mod.monotonic() - stamp) * 1000.0)

    def _publish_ltp(self, batch: list[tuple[int, int, str, int | None, int]]) -> None:
        """Latest-price key + fan-out, one pipeline round trip per batch.
        The KEY is what paper_broker fills from — it must always be SET."""
        sid_to_token = self._stock_to_token
        pipe = self.redis.pipeline(transaction=False)
        for stock_id, ts, price, _dv, _q in batch:
            pipe.set(LTP_KEY.format(stock_id=stock_id), price, ex=LTP_KEY_TTL_SECONDS)
            token = sid_to_token.get(stock_id)
            if token is not None:
                pipe.publish(
                    LTP_CHANNEL.format(instrument_token=token),
                    json.dumps(
                        {
                            "instrument_token": token,
                            "stock_id": stock_id,
                            "ltp": float(price),
                            "ts": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
                        }
                    ),
                )
        pipe.execute()

    def _enqueue_committed(self, events: list[dict[str, Any]]) -> None:
        """Committed candles go to the writer with a liveness-checked
        blocking put: never dropped while the writer lives; if the writer
        is DEAD, losing them is already a fact — fail loud and stop so the
        supervisor restarts instead of wedging the tick loop forever."""
        for e in events:
            if e["kind"] != "committed":
                continue
            self.stats["committed"] += 1
            while True:
                try:
                    self.writer_q.put(e, timeout=5.0)
                    break
                except queue.Full:
                    if not self.writer_alive():
                        self.stats["dropped_committed"] = (
                            self.stats.get("dropped_committed", 0) + 1
                        )
                        log.critical(
                            "writer thread dead; dropping committed candle %s — "
                            "stopping for supervisor restart", e,
                        )
                        if self.stop_event is not None:
                            self.stop_event.set()
                        break

    def _ffi_batch(
        self, ticks: list[dict[str, Any]]
    ) -> list[tuple[int, int, str, int | None, int]]:
        """Kite ticks → FFI tuples, dropping unusable (counted `skipped`)
        and snapshot-echo stale ticks (counted `stale`)."""
        batch: list[tuple[int, int, str, int | None, int]] = []
        for tick in ticks:
            ffi = tick_to_ffi(tick, self.token_map)
            if ffi is None:
                self.stats["skipped"] += 1
                continue
            if ffi[1] < self.min_tick_ts:
                self.stats["stale"] += 1
                continue
            batch.append(ffi)
        return batch

    def _apply_levels(self, payload: list[tuple[int, list[LevelDict], LevelMeta]]) -> None:
        """Engine accepts first, recording second — an "lv" line exists
        only for a set_levels the engine actually applied (same discipline
        as ticks; a replay set_levels failure is real divergence). One bad
        stock never blocks the rest (ANY exception — a TypeError from a
        malformed payload must not strand the chunk's other 99 stocks).
        A rejected stock is never acked, so the refresher re-sends it
        every cycle — repeat rejections stay loud in the log."""
        for sid, levels, meta in payload:
            try:
                self.book.set_levels(sid, levels)
            except Exception:
                log.exception("set_levels rejected for stock_id=%s", sid)
                continue
            self.stats["levels"] += 1
            self._record({"k": "lv", "sid": sid, "levels": levels})
            if meta:
                self.level_meta[sid] = meta
            else:
                self.level_meta.pop(sid, None)
            if self.on_levels_applied is not None:
                self.on_levels_applied(sid, levels)

    def _publish_alerts(self, events: list[dict[str, Any]]) -> None:
        """Trigger firings → the alerts Redis Stream (at-least-once class:
        one retry of the whole batch, then an error-level breadcrumb —
        never engine-blocking). ONE pipeline round trip per batch: an
        open-auction burst of hundreds of firings must not serialize
        hundreds of RTTs inside the latency-measured window."""
        alerts = [e for e in events if e["kind"] == "trigger"]
        if not alerts:
            return
        self.stats["triggers"] += len(alerts)
        all_fields: list[dict[str, Any]] = []
        for e in alerts:
            meta = self.level_meta.get(e["stock_id"], {}).get(e["id"], {})
            fields: dict[str, Any] = {
                "sid": e["stock_id"],
                "level_id": e["id"],
                "tag": e["tag"],
                "price": str(_money(e["price"])),
                "ts": e["ts"],
                "day": self.session_day,
                "source": str(meta.get("source", "")),
                "style": str(meta.get("style", "market")),
            }
            if meta.get("signal_id") is not None:
                fields["signal_id"] = meta["signal_id"]
            all_fields.append(fields)
        for attempt in (0, 1):
            try:
                pipe = self.redis.pipeline(transaction=False)
                for fields in all_fields:
                    pipe.xadd(
                        settings.live_alert_stream,
                        fields,
                        maxlen=settings.live_alert_maxlen,
                        approximate=True,
                    )
                pipe.execute()
                break
            except Exception:
                if attempt:
                    log.error(
                        "alert XADD failed — manual breadcrumb: %s",
                        json.dumps(all_fields), exc_info=True,
                    )

    def _publish_events(self, events: list[dict[str, Any]]) -> None:
        events = [e for e in events if e["kind"] != "trigger"]
        if not events:
            return
        pipe = self.redis.pipeline(transaction=False)
        for e in events:
            label = TF_LABEL[e["tf_minutes"]]
            table = TIMEFRAME_TABLE[label]
            pipe.publish(
                CANDLE_CHANNEL.format(table=table, stock_id=e["stock_id"]),
                json.dumps(
                    {
                        "stock_id": e["stock_id"],
                        "timeframe": label,
                        "time": datetime.fromtimestamp(e["time"], tz=UTC).isoformat(),
                        "open": float(_money(e["open"])),
                        "high": float(_money(e["high"])),
                        "low": float(_money(e["low"])),
                        "close": float(_money(e["close"])),
                        "volume": e["volume"],
                        "is_complete": e["kind"] == "committed",
                    }
                ),
            )
        pipe.execute()

    def _record(self, line: dict[str, Any]) -> None:
        """Fail-open: recording is observability, never load-bearing — a
        full disk must not cost a single candle (bug-hunter HIGH)."""
        if self.recorder is None:
            return
        try:
            self.recorder.write(json.dumps(line, separators=(",", ":")) + "\n")
        except OSError:
            log.exception("recorder write failed — disabling recording for this run")
            self.recorder = None


async def persist_committed(db: Any, event: dict[str, Any]) -> None:
    """Upsert one committed candle (Decimal-exact) — same SQL family as
    the v1 consumer, shared table whitelist."""
    from sqlalchemy import text

    label = TF_LABEL[event["tf_minutes"]]
    table = TIMEFRAME_TABLE[label]
    if table not in TIMEFRAME_TABLE.values():  # defence-in-depth
        raise ValueError(f"unknown candle table {table!r}")
    await db.execute(
        text(
            f"INSERT INTO {table} (time, stock_id, open, high, low, close, volume, is_complete)"  # noqa: S608
            " VALUES (:time, :sid, :open, :high, :low, :close, :volume, true)"
            " ON CONFLICT (time, stock_id) DO UPDATE SET"
            f"   high = GREATEST(EXCLUDED.high, {table}.high),"
            f"   low  = LEAST(EXCLUDED.low, {table}.low),"
            "   close = EXCLUDED.close,"
            # A restart re-mint (snapshot echo) carries volume 0/partial;
            # the fuller count wins — same monotone rule as high/low.
            f"   volume = GREATEST(EXCLUDED.volume, {table}.volume),"
            "   is_complete = true"
        ).bindparams(
            time=datetime.fromtimestamp(event["time"], tz=UTC),
            sid=event["stock_id"],
            open=_money(event["open"]),
            high=_money(event["high"]),
            low=_money(event["low"]),
            close=_money(event["close"]),
            volume=event["volume"],
        )
    )


def run_writer(writer_q: queue.Queue[dict[str, Any] | None]) -> None:
    """Writer thread: ONE long-lived event loop + ONE engine created
    in-thread (pooled connections never cross loops — the Celery lesson).

    Exits ONLY on the consumer's None sentinel — the consumer is the sole
    producer and owns the "no more events" signal, so a shutdown can never
    strand a committed candle in the queue (bug-hunter CRITICAL,
    2026-07-09). Each candle is retried before being logged as a manual-
    backfill breadcrumb; commit precedes the Celery trigger (visibility).
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    async def _persist_with_retry(engine: Any, event: dict[str, Any]) -> None:
        for attempt in range(3):
            try:
                async with AsyncSession(engine) as db:
                    await persist_committed(db, event)
                    await db.commit()
                _maybe_trigger_signal(event["stock_id"], TF_LABEL[event["tf_minutes"]])
                return
            except Exception:
                if attempt == 2:
                    log.error(
                        "writer: DROPPED committed candle after retries — "
                        "manual backfill breadcrumb: %s", json.dumps(event),
                        exc_info=True,
                    )
                else:
                    await asyncio.sleep(2.0 * (attempt + 1))

    async def main() -> None:
        engine = create_async_engine(settings.database_url, pool_size=2, max_overflow=0)
        try:
            loop = asyncio.get_running_loop()
            while True:
                event = await loop.run_in_executor(None, writer_q.get)
                if event is None:
                    return
                await _persist_with_retry(engine, event)
        finally:
            await engine.dispose()

    asyncio.new_event_loop().run_until_complete(main())


def run_consumer(
    state: WorkerState, in_q: queue.Queue[QueueItem], stop: threading.Event
) -> None:
    try:
        while not (stop.is_set() and in_q.empty()):
            try:
                item = in_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                state.process_item(item)
            except Exception:
                # One bad batch must never end live data for the day.
                log.exception("consumer: batch failed; continuing")
        # Final flush: on_time only commits ENDED buckets — safe any time.
        try:
            state.process_item(("pulse", int(time_mod.time()), None))
        except Exception:
            log.exception("consumer: final flush failed")
    finally:
        # The consumer owns the downstream lifecycle: recorder closes here
        # (main must not close it under a live consumer), and the writer's
        # None sentinel goes in strictly AFTER the final flush.
        if state.recorder is not None:
            try:
                state.recorder.close()
            except Exception:
                log.exception("consumer: recorder close failed")
        state.writer_q.put(None)


def run_pulser(in_q: queue.Queue[QueueItem], stop: threading.Event) -> None:
    while not stop.wait(_PULSE_INTERVAL_S):
        try:
            in_q.put_nowait(("pulse", int(time_mod.time()), None))
        except queue.Full:
            pass  # the next pulse is a second away


def enqueue_ticks(in_q: queue.Queue[QueueItem], ticks: list[dict[str, Any]]) -> None:
    """Drop-oldest for tick batches (stale LTP beats a crashed callback);
    committed candles are protected downstream, not here."""
    dropped = 0
    stamp = time_mod.monotonic()
    while True:
        try:
            in_q.put_nowait(("ticks", ticks, stamp))
            break
        except queue.Full:
            # Drain one and retry — looped, because the pulser can refill
            # the freed slot between our get and put, and an exception here
            # would land inside the Twisted/KiteTicker callback.
            try:
                in_q.get_nowait()
                dropped += 1
            except queue.Empty:
                continue
    if dropped:
        log.warning("live-worker queue full; dropped %d oldest item(s)", dropped)


async def startup_gap_fill(
    db: Any, access_token: str, token_map: dict[int, int]
) -> None:
    """REST-backfill gaps for the subscription list, then COMMIT — the
    session-close rollback silently discarded every fetched row before
    (bug-hunter HIGH, 2026-07-09: gap_fill never commits and this is its
    only caller)."""
    from app.broker.gap_fill import detect_and_fill_gaps

    for instrument_token, stock_id in token_map.items():
        try:
            await detect_and_fill_gaps(
                db, access_token, instrument_token, stock_id,
                timeframes=["5m", "15m", "1h"],
            )
        except Exception:
            log.exception("gap-fill failed for stock_id=%s", stock_id)
    await db.commit()


async def _bootstrap(
    gap_fill: bool,
) -> tuple[str, dict[int, int], LevelDirectory, list[Any]] | None:
    """Fetch the active token + instrument map, build the trigger-level
    directory (3.5), and optionally gap-fill."""
    from app.broker.kite_client import get_active_token
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        token = await get_active_token(db, user_id=1)
        if token is None:
            return None
        token_map = await _build_token_stock_map(db, token.access_token)
        if gap_fill and token_map:
            await startup_gap_fill(db, token.access_token, token_map)
        directory = await build_directory(
            db, datetime.now(tz=UTC), sorted(token_map.values())
        )
        initial_levels = await directory.refresh(db)
    return token.access_token, token_map, directory, initial_levels


def run_refresher(
    directory: LevelDirectory, in_q: queue.Queue[QueueItem], stop: threading.Event
) -> None:
    """Signal-level refresh thread: its own event loop + its own engine
    (the writer-thread pattern — pooled connections never cross loops).
    Changed level sets are enqueued as "levels" items so the consumer
    applies + records them in stream order with ticks. The ACK lives with
    the consumer (`WorkerState.on_levels_applied` → `mark_sent`): a full
    queue, a drop-oldest eviction, or an engine rejection all leave the
    stock unacked and it re-sends next cycle — never silently divergent."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    async def _changed(engine: Any) -> list[tuple[int, list[LevelDict], LevelMeta]]:
        async with AsyncSession(engine) as db:
            return await directory.refresh(db)

    loop = asyncio.new_event_loop()
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    try:
        while not stop.wait(settings.live_level_refresh_s):
            try:
                changed = loop.run_until_complete(_changed(engine))
            except Exception:
                log.exception("level refresh failed; retrying next cycle")
                continue
            for sid, levels, meta in changed:
                try:
                    in_q.put_nowait(("levels", [(sid, levels, meta)], None))
                except queue.Full:
                    log.warning("queue full during level refresh; deferring")
                    break
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()



def _make_ticker(
    access_token: str,
    token_map: dict[int, int],
    in_q: queue.Queue[QueueItem],
    on_close: Any,
) -> Any:
    from kiteconnect import KiteTicker

    ticker = KiteTicker(
        api_key=settings.kite_api_key, access_token=access_token,
        reconnect=True, reconnect_max_tries=50,
    )
    ticker.on_ticks = lambda ws, ticks: enqueue_ticks(in_q, ticks)
    ticker.on_connect = lambda ws, resp: (
        ws.subscribe(list(token_map)), ws.set_mode(ws.MODE_FULL, list(token_map))
    )
    ticker.on_close = on_close
    return ticker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="tick-to-tick live worker")
    parser.add_argument("--gap-fill", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    boot = asyncio.run(_bootstrap(args.gap_fill))
    if boot is None:
        log.critical("no active Kite token — run scripts/kite_login.py, then restart")
        return EXIT_NO_TOKEN
    access_token, token_map, directory, initial_levels = boot

    import redis as redis_sync
    import tradecore

    today = datetime.now(tz=UTC).astimezone(_IST).date()
    open_ts, close_ts = session_bounds_ist(today)
    book = tradecore.LiveBook(open_ts, close_ts, TF_MINUTES)
    book.ensure_instruments(sorted(token_map.values()))

    recorder: TextIO | None = None
    record_path = settings.live_record_path
    if record_path:
        # Line-buffered: a hard crash loses at most the in-flight line.
        recorder = open(record_path, "a", buffering=1, encoding="utf-8")  # noqa: SIM115
        # Header makes the recording self-describing — replay (3.4) builds
        # an identical LiveBook from it. Appending to yesterday's file adds
        # a new header line; replay treats each header as a session start.
        # Leading newline isolates any torn tail a crashed run left behind
        # (replay skips blank lines; a fragment stays on its own line).
        recorder.write("\n")
        recorder.write(
            json.dumps(
                {
                    "k": "h",
                    "day": today.isoformat(),
                    "open": open_ts,
                    "close": close_ts,
                    "tfs": TF_MINUTES,
                    "min_tick_ts": int(time_mod.time()) - 120,
                },
                separators=(",", ":"),
            )
            + "\n"
        )

    in_q: queue.Queue[QueueItem] = queue.Queue(maxsize=_QUEUE_MAX)
    writer_q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=_QUEUE_MAX)
    stop = threading.Event()
    exit_code = 0

    writer_thread = threading.Thread(target=run_writer, args=(writer_q,), name="writer")
    state = WorkerState(
        book=book,
        token_map=token_map,
        redis=redis_sync.from_url(settings.redis_url, decode_responses=True),
        writer_q=writer_q,
        recorder=recorder,
        # Kite's subscribe snapshot echoes each instrument's LAST tick,
        # possibly minutes old after a mid-session restart — 120s grace.
        min_tick_ts=int(time_mod.time()) - 120,
        writer_alive=writer_thread.is_alive,
        stop_event=stop,
        session_day=today.isoformat(),
        on_levels_applied=directory.mark_sent,
    )

    # Initial trigger levels precede the first tick in the queue (and so
    # in the recording): the consumer applies them before any tick lands.
    # The consumer acks each applied stock via on_levels_applied.
    chunk_size = 100
    for i in range(0, len(initial_levels), chunk_size):
        in_q.put(("levels", initial_levels[i : i + chunk_size], None))

    def on_close(ws: Any, code: Any, reason: Any) -> None:
        nonlocal exit_code
        if stop.is_set():
            return  # our own ticker.stop() during clean shutdown
        log.critical("KiteTicker closed code=%s reason=%s — exiting for restart", code, reason)
        exit_code = EXIT_WS_DIED
        stop.set()

    ticker = _make_ticker(access_token, token_map, in_q, on_close)

    threads = [
        threading.Thread(target=run_consumer, args=(state, in_q, stop), name="consumer"),
        writer_thread,
        threading.Thread(target=run_pulser, args=(in_q, stop), name="pulser", daemon=True),
        threading.Thread(
            target=run_refresher, args=(directory, in_q, stop), name="refresher",
            daemon=True,
        ),
    ]
    for t in threads:
        t.start()
    ticker.connect(threaded=True)
    log.info("live-worker up: %d instruments, session %s", len(token_map), today)

    _run_until_done(stop, today)
    stop.set()
    try:
        ticker.stop()
    except Exception:
        log.debug("ticker close raised; ignoring")
    threads[0].join(timeout=60)  # consumer: drains, flushes, sends sentinel
    threads[1].join(timeout=60)  # writer: exits on the sentinel
    log.info("live-worker stats: %s latency: %s", state.stats, state.latency.summary())
    return exit_code


def _run_until_done(stop: threading.Event, today: date) -> None:
    """Block until the session is long over, the WS dies, or Ctrl-C."""
    end_of_day = datetime.combine(today, SESSION_CLOSE, tzinfo=_IST) + timedelta(minutes=10)
    try:
        while not stop.is_set():
            if datetime.now(tz=UTC) >= end_of_day:
                log.info("session over — clean shutdown")
                return
            stop.wait(5)
    except KeyboardInterrupt:
        log.info("interrupted — clean shutdown")


if __name__ == "__main__":
    raise SystemExit(main())
