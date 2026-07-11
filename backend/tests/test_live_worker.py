"""Live-worker seams (Phase 3 slice 3.3).

The consumer is driven SYNCHRONOUSLY (threads are thin wrappers), with a
REAL tradecore.LiveBook and a redis spy — the seam between Kite tick
dicts, the Rust engine, Redis contracts, and the writer queue is what
these pin. Persistence runs against the real test DB.
"""

import json
import queue
import threading
import time as time_mod
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import tradecore
from app.broker.live_worker import (
    TF_MINUTES,
    LatencyHistogram,
    WorkerState,
    enqueue_ticks,
    persist_committed,
    run_writer,
    session_bounds_ist,
    startup_gap_fill,
    tick_to_ffi,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 7, 9)
OPEN_TS, CLOSE_TS = session_bounds_ist(DAY)
TOKEN_MAP = {777: 42}  # instrument_token → stock_id


class _SyncRedisSpy:
    """Records the sync pipeline the hot path builds. `pubsub` is the set
    of channels the spy reports as having live subscribers (the 3.5 perf
    fix gates publishes on it)."""

    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.publish_calls: list[tuple[str, str]] = []
        self.pubsub: list[str] = []

    def pipeline(self, transaction: bool = True) -> "_SyncRedisSpy":
        return self

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.set_calls.append((key, value, ex))

    def publish(self, channel: str, payload: str) -> None:
        self.publish_calls.append((channel, payload))

    def pubsub_channels(self, pattern: str = "*") -> list[str]:
        prefix = pattern.rstrip("*")
        return [c for c in self.pubsub if c.startswith(prefix)]

    def execute(self) -> None:
        pass


def _watch_all(state) -> None:
    """Mark stock 42 / token 777's channels as live-subscribed."""
    from app.broker.candle_aggregator import TIMEFRAME_TABLE

    state.watched_channels = {"ltp:777"} | {
        f"candle:{table}:42" for table in TIMEFRAME_TABLE.values()
    }


def _state(tmp_path=None) -> tuple[WorkerState, _SyncRedisSpy, "queue.Queue"]:
    book = tradecore.LiveBook(OPEN_TS, CLOSE_TS, TF_MINUTES)
    book.ensure_instruments([42])
    spy = _SyncRedisSpy()
    writer_q: queue.Queue = queue.Queue()
    recorder = open(tmp_path / "rec.jsonl", "a", encoding="utf-8") if tmp_path else None
    return WorkerState(
        book=book, token_map=TOKEN_MAP, redis=spy, writer_q=writer_q, recorder=recorder
    ), spy, writer_q


def _tick(ts_ist_h: int, ts_ist_m: int, price: str, day_vol: int) -> dict:
    # naive host-local timestamp, exactly as kiteconnect delivers
    aware = datetime.combine(DAY, datetime.min.time(), tzinfo=IST).replace(
        hour=ts_ist_h, minute=ts_ist_m
    )
    return {
        "instrument_token": 777,
        "last_price": price,
        "volume_traded": day_vol,
        "exchange_timestamp": aware.astimezone().replace(tzinfo=None),
    }


class TestSessionBounds:
    def test_standard_session_epochs(self) -> None:
        open_ts, close_ts = session_bounds_ist(DAY)
        assert datetime.fromtimestamp(open_ts, tz=UTC).astimezone(IST).strftime(
            "%H:%M"
        ) == "09:15"
        assert close_ts - open_ts == 6 * 3600 + 15 * 60


class TestTickToFfi:
    def test_naive_host_local_timestamp_converts(self) -> None:
        ffi = tick_to_ffi(_tick(9, 30, "101.55", 1000), TOKEN_MAP)
        assert ffi is not None
        sid, ts, price, dv, _qty = ffi
        assert (sid, price, dv) == (42, "101.55", 1000)
        assert datetime.fromtimestamp(ts, tz=UTC).astimezone(IST).strftime("%H:%M") == "09:30"

    def test_unknown_instrument_and_missing_price_skip(self) -> None:
        assert tick_to_ffi({"instrument_token": 1, "last_price": 5}, TOKEN_MAP) is None
        assert tick_to_ffi({"instrument_token": 777}, TOKEN_MAP) is None


class TestConsumerSeam:
    def test_ltp_contract_and_forming_publish(self, tmp_path) -> None:
        state, spy, writer_q = _state(tmp_path)
        _watch_all(state)  # publishes are subscriber-gated since the 3.5 perf fix
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))

        assert spy.set_calls == [("ltp:42", "101.55", 600)]
        channels = [c for c, _ in spy.publish_calls]
        assert "ltp:777" in channels
        forming = [
            json.loads(p) for c, p in spy.publish_calls if c.startswith("candle:")
        ]
        assert len(forming) == 4 and all(not f["is_complete"] for f in forming)
        assert writer_q.empty()
        state.recorder.flush()
        lines = [
            json.loads(line) for line in open(tmp_path / "rec.jsonl", encoding="utf-8")
        ]
        assert lines[0]["k"] == "t" and lines[0]["p"] == "101.55"

    def test_committed_candle_reaches_writer_queue_exactly(self, tmp_path) -> None:
        state, spy, writer_q = _state(tmp_path)
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))
        state.process_item(("ticks", [_tick(9, 21, "102.00", 1400)]))  # next 1m+5m bucket

        committed = []
        while not writer_q.empty():
            committed.append(writer_q.get_nowait())
        assert {e["tf_minutes"] for e in committed} == {1, 5}
        one_m = next(e for e in committed if e["tf_minutes"] == 1)
        assert Decimal(one_m["close"]) / 10**4 == Decimal("101.55")
        assert datetime.fromtimestamp(one_m["time"], tz=UTC).astimezone(IST).strftime(
            "%H:%M"
        ) == "09:16"

    def test_pulse_commits_ended_buckets_and_is_recorded(self, tmp_path) -> None:
        state, spy, writer_q = _state(tmp_path)
        state.process_item(("ticks", [_tick(15, 29, "99.00", 500)]))
        state.process_item(("pulse", CLOSE_TS))

        committed = []
        while not writer_q.empty():
            committed.append(writer_q.get_nowait())
        # session-last candle closes on every timeframe without a next tick
        assert sorted(e["tf_minutes"] for e in committed) == [1, 5, 15, 60]
        state.recorder.flush()
        kinds = [
            json.loads(line)["k"] for line in open(tmp_path / "rec.jsonl", encoding="utf-8")
        ]
        assert kinds == ["t", "p"]

    def test_bad_batch_counts_skipped(self, tmp_path) -> None:
        state, spy, _ = _state(tmp_path)
        state.process_item(("ticks", [{"instrument_token": 999, "last_price": 1}]))
        assert state.stats["skipped"] == 1
        assert spy.set_calls == []

    def test_publishes_gated_off_without_subscribers(self, tmp_path) -> None:
        """Perf-audit fix 1 (2026-07-10): payloads for channels nobody
        subscribed are neither built nor published — but the LTP KEY is
        ALWAYS SET (paper_broker contract)."""
        state, spy, _ = _state(tmp_path)
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))
        assert spy.set_calls == [("ltp:42", "101.55", 600)]
        assert spy.publish_calls == []

    def test_pulse_refreshes_watched_channels_from_pubsub(self, tmp_path) -> None:
        state, spy, _ = _state(tmp_path)
        spy.pubsub = ["ltp:777", "candle:ohlcv_1m:42", "alerts:unrelated"]
        state.process_item(("pulse", OPEN_TS + 60))
        assert state.watched_channels == {"ltp:777", "candle:ohlcv_1m:42"}
        # a subscribed channel now receives; unsubscribed ones still don't
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))
        channels = {c for c, _ in spy.publish_calls}
        assert channels == {"ltp:777", "candle:ohlcv_1m:42"}

    def test_latency_split_observes_dwell_and_processing(self, tmp_path) -> None:
        state, _, _ = _state(tmp_path)
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)], time_mod.monotonic()))
        assert state.latency.n == 1
        assert state.dwell.n == 1
        assert state.processing.n == 1
        # end-to-end >= processing component by construction
        assert state.latency.max_ms >= state.processing.max_ms


class TestEnqueueBackpressure:
    def test_drop_oldest_when_full(self) -> None:
        q: queue.Queue = queue.Queue(maxsize=2)
        enqueue_ticks(q, [{"n": 1}])
        enqueue_ticks(q, [{"n": 2}])
        enqueue_ticks(q, [{"n": 3}])  # drops the n=1 batch
        items = [q.get_nowait()[1][0]["n"] for _ in range(2)]
        assert items == [2, 3]


class TestPersistCommitted:
    async def test_upserts_decimal_exact_and_marks_complete(
        self, db: AsyncSession
    ) -> None:
        from tests.helpers import make_stock

        stock = await make_stock(db, symbol="LIVEW1")
        event = {
            "stock_id": stock.id,
            "kind": "committed",
            "tf_minutes": 60,
            "time": OPEN_TS,
            "open": 1015500,
            "high": 1020000,
            "low": 1010000,
            "close": 1018250,
            "volume": 12345,
        }
        await persist_committed(db, event)
        await db.commit()
        row = (
            await db.execute(
                text("SELECT time, open, high, low, close, volume, is_complete"
                     " FROM ohlcv_1h WHERE stock_id = :sid"),
                {"sid": stock.id},
            )
        ).one()
        assert (row.open, row.high, row.low, row.close) == (
            Decimal("101.5500"), Decimal("102.0000"),
            Decimal("101.0000"), Decimal("101.8250"),
        )
        assert row.volume == 12345 and row.is_complete is True
        assert row.time == datetime.fromtimestamp(OPEN_TS, tz=UTC)

    async def test_upsert_is_idempotent_on_conflict(self, db: AsyncSession) -> None:
        from tests.helpers import make_stock

        stock = await make_stock(db, symbol="LIVEW2")
        event = {
            "stock_id": stock.id, "kind": "committed", "tf_minutes": 60,
            "time": OPEN_TS, "open": 1000000, "high": 1010000,
            "low": 990000, "close": 1005000, "volume": 100,
        }
        await persist_committed(db, event)
        await persist_committed(db, {**event, "high": 1020000, "volume": 150})
        # a restart re-mint (snapshot echo) carries volume 0 — the fuller
        # count must win, never be clobbered (bug-hunter, 2026-07-09)
        await persist_committed(db, {**event, "volume": 0})
        await db.commit()
        row = (
            await db.execute(
                text("SELECT high, volume FROM ohlcv_1h WHERE stock_id = :sid"),
                {"sid": stock.id},
            )
        ).one()
        assert (row.high, row.volume) == (Decimal("102.0000"), 150)


class TestBugHunterRegressions:
    """Contracts pinned after the 2026-07-09 bug-hunter pass on 3.3."""

    def test_writer_exits_only_on_sentinel_never_strands_candles(
        self, monkeypatch
    ) -> None:
        """CRITICAL: the old writer exited on (stop AND empty) and raced the
        consumer's final flush — a candle enqueued after its exit was
        stranded forever. The sentinel contract: the writer drains
        EVERYTHING until the consumer's None, regardless of timing."""
        import app.broker.live_worker as lw

        persisted: list[dict] = []

        async def fake_persist(db, event) -> None:
            persisted.append(event)

        monkeypatch.setattr(lw, "persist_committed", fake_persist)
        monkeypatch.setattr(lw, "_maybe_trigger_signal", lambda sid, tf: None)

        q: queue.Queue = queue.Queue()
        writer = threading.Thread(target=run_writer, args=(q,))
        writer.start()
        time_mod.sleep(0.5)  # old code: already exited by now (queue empty)
        event = {"stock_id": 1, "kind": "committed", "tf_minutes": 1,
                 "time": OPEN_TS, "open": 1, "high": 1, "low": 1, "close": 1,
                 "volume": 1}
        q.put(event)
        q.put(None)
        writer.join(timeout=10)
        assert not writer.is_alive()
        assert persisted == [event]

    def test_redis_outage_never_starves_the_engine(self, tmp_path) -> None:
        """MEDIUM: publishes ran BEFORE the engine call and unprotected —
        a redis blip dropped the batch pre-engine while the recorder had
        already logged it (replay divergence). Engine-first now: candles
        keep forming/committing and reach the writer queue with redis down."""

        class _DownRedis(_SyncRedisSpy):
            def execute(self) -> None:
                raise ConnectionError("redis down")

        book = tradecore.LiveBook(OPEN_TS, CLOSE_TS, TF_MINUTES)
        book.ensure_instruments([42])
        writer_q: queue.Queue = queue.Queue()
        state = WorkerState(
            book=book, token_map=TOKEN_MAP, redis=_DownRedis(), writer_q=writer_q
        )
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))
        state.process_item(("ticks", [_tick(9, 17, "102.00", 1400)]))
        assert state.stats["ticks"] == 2
        committed = writer_q.get_nowait()
        assert committed["tf_minutes"] == 1
        assert Decimal(committed["close"]) / 10**4 == Decimal("101.55")

    def test_stale_snapshot_ticks_skipped(self) -> None:
        """MEDIUM: Kite's subscribe snapshot echoes each instrument's LAST
        tick after a mid-session restart — a fresh book would re-mint an
        already-persisted bucket. Ticks older than min_tick_ts are counted
        and dropped before the engine."""
        book = tradecore.LiveBook(OPEN_TS, CLOSE_TS, TF_MINUTES)
        book.ensure_instruments([42])
        state = WorkerState(
            book=book, token_map=TOKEN_MAP, redis=_SyncRedisSpy(),
            writer_q=queue.Queue(), min_tick_ts=OPEN_TS + 3600,
        )
        state.process_item(("ticks", [_tick(9, 30, "101.00", 100)]))  # pre-cutoff
        assert state.stats == {**state.stats, "stale": 1, "ticks": 0}

    async def test_startup_gap_fill_commits_the_work(
        self, db: AsyncSession, monkeypatch
    ) -> None:
        """HIGH: gap_fill never commits and the bootstrap session's close
        rolled everything back — rows were fetched, logged, and silently
        discarded. startup_gap_fill must leave them COMMITTED."""
        from tests.helpers import make_stock

        stock = await make_stock(db, symbol="GAPFX")

        async def fake_fill(dbs, token, instrument_token, stock_id, timeframes):
            await dbs.execute(
                text(
                    "INSERT INTO ohlcv_5m (time, stock_id, open, high, low,"
                    " close, volume, is_complete) VALUES"
                    " (:t, :sid, 1, 1, 1, 1, 1, true)"
                ),
                {"t": datetime.fromtimestamp(OPEN_TS, tz=UTC), "sid": stock_id},
            )
            return {"5m": 1}

        import app.broker.gap_fill as gf

        monkeypatch.setattr(gf, "detect_and_fill_gaps", fake_fill)
        await startup_gap_fill(db, "token", {777: stock.id})

        await db.rollback()  # committed work must survive a rollback
        n = (
            await db.execute(
                text("SELECT count(*) FROM ohlcv_5m WHERE stock_id = :sid"),
                {"sid": stock.id},
            )
        ).scalar()
        assert n == 1


class TestLatencyHistogram:
    def test_buckets_and_quantiles(self) -> None:
        h = LatencyHistogram()
        for ms in (0.4, 0.8, 1.5, 3.0, 8.0, 60.0):
            h.observe(ms)
        assert h.n == 6
        assert h.summary()["p50_ms"] == 2.0  # 3rd of 6 falls in the <=2ms bucket
        assert h.summary()["p99_ms"] == 100.0
        assert h.summary()["max_ms"] == 60.0
        empty = LatencyHistogram()
        assert empty.summary() == {"n": 0, "p50_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}

    def test_process_item_observes_stamped_batches(self, tmp_path) -> None:
        state, _, _ = _state(tmp_path)
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)], time_mod.monotonic()))
        state.process_item(("ticks", [_tick(9, 17, "101.60", 1100)]))  # unstamped: not observed
        assert state.latency.n == 1
        assert state.latency.summary()["max_ms"] >= 0.0


class TestRecordReplayFidelity:
    def test_recording_reproduces_the_writer_queue_stream(self, tmp_path) -> None:
        """The 3.4 contract at the worker seam: replaying the recorded
        tick+pulse stream through a fresh LiveBook yields EXACTLY the
        committed events the live consumer sent to the writer — including
        when the live run skipped unknown-instrument and stale ticks
        (they are not recorded, so replay never sees them)."""
        from app.broker.replay import replay_file

        state, _, writer_q = _state(tmp_path)
        state.min_tick_ts = OPEN_TS  # arm the stale filter
        header = {
            "k": "h", "day": DAY.isoformat(), "open": OPEN_TS,
            "close": CLOSE_TS, "tfs": TF_MINUTES, "min_tick_ts": OPEN_TS,
        }
        rec = tmp_path / "worker_rec.jsonl"
        with open(rec, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(header, separators=(",", ":")) + "\n")
        state.recorder = open(rec, "a", encoding="utf-8")

        stale = _tick(9, 16, "50.00", 10)
        stale["exchange_timestamp"] = datetime(2020, 1, 1, 12, 0)  # pre-min_tick_ts
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000), stale]))
        state.process_item(("ticks", [{"instrument_token": 999, "last_price": 1}]))
        state.process_item(("ticks", [_tick(9, 21, "102.00", 1400)]))
        state.process_item(("pulse", CLOSE_TS, None))
        state.recorder.close()
        state.recorder = None

        live_committed = []
        while not writer_q.empty():
            live_committed.append(writer_q.get_nowait())

        events, _digest = replay_file(rec)
        replayed_committed = [
            {k: v for k, v in e.items() if k not in ("day", "kind")}
            for e in events
            if e["kind"] == "committed"
        ]
        live_stripped = [
            {k: v for k, v in e.items() if k != "kind"} for e in live_committed
        ]
        assert replayed_committed == live_stripped
        assert state.stats["stale"] == 1 and state.stats["skipped"] == 1


class TestRecorderFailOpen:
    def test_recorder_failure_never_costs_a_candle(self, tmp_path) -> None:
        """bug-hunter HIGH (2026-07-10): a recorder write failure aborted
        the batch BEFORE the engine — disk-full would have starved candles
        and LTP for the rest of the session. Recording must fail open."""

        class _FullDisk:
            def write(self, _line: str) -> None:
                raise OSError("no space left on device")

            def close(self) -> None:
                pass

        state, spy, writer_q = _state()
        state.recorder = _FullDisk()
        state.process_item(("ticks", [_tick(9, 16, "101.55", 1000)]))
        state.process_item(("ticks", [_tick(9, 21, "102.00", 1400)]))

        assert state.recorder is None  # disabled, not fatal
        assert state.stats["ticks"] == 2
        committed = writer_q.get_nowait()
        assert Decimal(committed["close"]) / 10**4 == Decimal("101.55")
        assert spy.set_calls  # LTP kept flowing
