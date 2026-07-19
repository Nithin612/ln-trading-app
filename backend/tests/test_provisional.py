"""Provisional confidence + per-style leaderboards (Phase 3, 3.5-deferred).

Covers the pinned design's load-bearing invariants (ledger §Decisions
2026-07-11):
  - CONVERGENCE: scoring the forming-appended window equals scoring the
    same window with that bar committed — parity by construction.
  - Window canon: ≤299 completed + forming; re-minted buckets superseded.
  - Hot-set assembly (signal > trigger > watchlist) with logged clipping.
  - Leaderboards: TTL'd SET + PUBLISH, confidence-desc None-last ordering,
    top-N clip that NEVER drops active-signal rows.
  - run_cycle end-to-end through the REAL tradecore LiveBook: the
    published row equals score_signal on the exact same window (the seam,
    both sides).
  - REST reconciliation endpoint.

Everything runs on the real test Postgres + real Redis (no seam mocks).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
import redis as redis_sync
from app.broker.provisional import (
    ALL_PROVISIONAL_STYLES,
    LEADERBOARD_CHANNEL,
    LEADERBOARD_KEY,
    _in_session,
    append_forming,
    forming_daily_bar,
    load_hot_set,
    publish_leaderboards,
    run_cycle,
    score_pair,
)
from app.core.config import settings
from app.models.signal import Signal
from app.models.watchlist import Watchlist, WatchlistItem
from app.services.signal_service import score_signal
from sqlalchemy import text

from tests.helpers import create_test_user, make_profile, make_stock

# 2026-07-16 (Wednesday): session 09:15–15:30 IST = 03:45–10:00 UTC.
DAY = date(2026, 7, 16)
OPEN_UTC = datetime(2026, 7, 16, 3, 45, tzinfo=UTC)
CLOSE_UTC = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)
# Forming 5m bucket start: 06:00 UTC = 11:30 IST (27 buckets past open).
FORMING_T = datetime(2026, 7, 16, 6, 0, tzinfo=UTC)
NOW = datetime(2026, 7, 16, 6, 3, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fresh_cycle_cache():
    """run_cycle memoizes universes/flows on the function object — a
    leaked cache would let one test's universe answer another's."""
    run_cycle.__dict__.pop("_cache", None)
    yield
    run_cycle.__dict__.pop("_cache", None)


@pytest.fixture
def sync_redis():
    r = redis_sync.from_url(settings.redis_url, decode_responses=True)
    yield r
    for key in r.scan_iter("provisional:leaderboard:*"):
        r.delete(key)
    r.close()


def choppy(n: int = 120, start: float = 100.0, end: datetime = FORMING_T) -> pd.DataFrame:
    """Deterministic weak-ADX chop (±0.4% alternating 3-bar runs), 4dp
    prices so the DB round-trip (Numeric(12,4)) is byte-exact. Scores
    (SELL, 43) through the frozen engine at min_confidence=0."""
    times = [end - timedelta(minutes=5 * (n - 1 - i)) for i in range(n)]
    closes, price = [], start
    for i in range(n):
        price *= 1 + (0.004 if (i // 3) % 2 == 0 else -0.004)
        closes.append(round(price, 4))
    closes_a = np.array(closes)
    opens = np.concatenate([[start], closes_a[:-1]]).round(4)
    highs = (np.maximum(opens, closes_a) * 1.0015).round(4)
    lows = (np.minimum(opens, closes_a) * 0.9985).round(4)
    vols = np.full(n, 15000)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_a,
         "volume": vols.astype(int)},
        index=pd.DatetimeIndex(times),
    )


def rollover_marubozu(n: int = 120, start: float = 100.0,
                      end: datetime = FORMING_T) -> pd.DataFrame:
    """Slow rise, 3-bar stall, then a huge red marubozu on 3.5× volume.
    Fires MARUBOZU_BEARISH −0.8 + volume-confirm + bearish ADX under a
    strong-ADX regime → (SELL, 66) ≥ effective gate 65 at min_confidence
    70 — a REAL profile (the config schema floors min_confidence at 70)
    sees this stock on its leaderboard. 4dp prices: DB round-trip exact."""
    times = [end - timedelta(minutes=5 * (n - 1 - i)) for i in range(n)]
    closes, price = [], start
    for i in range(n - 1):
        price *= 1 + (0.0015 if i < n - 4 else -0.002)
        closes.append(round(price, 4))
    closes.append(round(closes[-1] * 0.97, 4))
    closes_a = np.array(closes)
    opens = np.concatenate([[start], closes_a[:-1]]).round(4)
    highs = (np.maximum(opens, closes_a) * 1.0005).round(4)
    lows = (np.minimum(opens, closes_a) * 0.9995).round(4)
    highs[-1] = opens[-1]  # marubozu: open == high,
    lows[-1] = closes_a[-1]  # close == low
    vols = np.full(n, 12000)
    vols[-1] = 42000
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_a,
         "volume": vols.astype(int)},
        index=pd.DatetimeIndex(times),
    )


async def _seed_5m(db, sid: int, frame: pd.DataFrame) -> None:
    for t, row in frame.iterrows():
        await db.execute(
            text(
                "INSERT INTO ohlcv_5m (time, stock_id, open, high, low, close,"
                " volume, is_complete) VALUES (:t, :sid, :o, :h, :l, :c, :v, true)"
            ),
            {
                "t": t, "sid": sid,
                "o": Decimal(f"{row['open']:.4f}"), "h": Decimal(f"{row['high']:.4f}"),
                "l": Decimal(f"{row['low']:.4f}"), "c": Decimal(f"{row['close']:.4f}"),
                "v": int(row["volume"]),
            },
        )
    await db.commit()


async def _seed_signal(db, sid: int, classification: str = "swing",
                       timeframe: str = "1h", profile_key: str | None = None) -> Signal:
    signal = Signal(
        stock_id=sid,
        direction="BUY",
        classification=classification,
        timeframe=timeframe,
        entry_price=Decimal("100"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("104"),
        suggested_qty=10,
        confidence_pct=75,
        factor_scores={},
        headline="provisional test signal",
        status="active",
        validity_until=datetime(2030, 1, 1, tzinfo=UTC),
        profile_key=profile_key,
    )
    db.add(signal)
    await db.commit()
    return signal


# ── Session gate ──────────────────────────────────────────────────────────────


class TestSessionGate:
    def test_in_session_boundaries(self) -> None:
        ist = timedelta(hours=5, minutes=30)

        def at(h: int, m: int, day: date = DAY) -> datetime:
            return datetime.combine(day, time(h, m), tzinfo=UTC) - ist

        assert not _in_session(at(9, 14))
        assert _in_session(at(9, 15))
        assert _in_session(at(15, 35))  # +5 min drain grace
        assert not _in_session(at(15, 36))
        assert not _in_session(at(11, 0, date(2026, 7, 18)))  # Saturday


# ── Forming daily bar (own-bars principle) ────────────────────────────────────


class TestFormingDailyBar:
    COMMITTED = {
        "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0,
        "volume": 50_000,
        "last_time": datetime(2026, 7, 16, 5, 55, tzinfo=UTC),
    }
    FORMING = {  # raw i64·1e-4 money, like a forming_snapshot event
        "time": int(FORMING_T.timestamp()),
        "open": 104_5000, "high": 106_0000, "low": 104_0000, "close": 105_5000,
        "volume": 3_000,
    }

    def test_committed_only(self) -> None:
        t, bar = forming_daily_bar(self.COMMITTED, None, DAY)
        assert t == datetime(2026, 7, 16, tzinfo=UTC)  # 1d storage canon
        assert bar == {"open": 100.0, "high": 105.0, "low": 99.0,
                       "close": 104.0, "volume": 50_000}

    def test_forming_only(self) -> None:
        t, bar = forming_daily_bar(None, self.FORMING, DAY)
        assert bar == {"open": 104.5, "high": 106.0, "low": 104.0,
                       "close": 105.5, "volume": 3_000}

    def test_merge(self) -> None:
        _, bar = forming_daily_bar(self.COMMITTED, self.FORMING, DAY)
        assert bar == {"open": 100.0, "high": 106.0, "low": 99.0,
                       "close": 105.5, "volume": 53_000}

    def test_overlapping_forming_bucket_skipped(self) -> None:
        """A restart re-mint can leave the committed set already covering
        the forming bucket — the forming fragment must not double-count."""
        overlap = dict(self.FORMING, time=int(
            datetime(2026, 7, 16, 5, 55, tzinfo=UTC).timestamp()))
        _, bar = forming_daily_bar(self.COMMITTED, overlap, DAY)
        assert bar["volume"] == 50_000 and bar["close"] == 104.0

    def test_nothing_yields_none(self) -> None:
        assert forming_daily_bar(None, None, DAY) is None


# ── Window canon ──────────────────────────────────────────────────────────────


class TestAppendForming:
    def test_caps_window_at_300(self) -> None:
        frame = choppy(n=310, end=FORMING_T - timedelta(minutes=5))
        bar = {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5,
               "volume": 500}
        out = append_forming(frame, FORMING_T, bar)
        assert len(out) == 300  # 299 completed + forming
        assert out.index[-1] == FORMING_T
        assert out.index[0] == frame.index[11]  # oldest 11 dropped
        assert float(out.iloc[-1]["close"]) == 100.5

    def test_supersedes_reminted_bucket(self) -> None:
        """Rows at/after the forming bar's time are the SAME bucket seen
        by an earlier partial commit — the live forming bar supersedes."""
        frame = choppy(n=60, end=FORMING_T)  # last row sits AT forming time
        bar = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 9}
        out = append_forming(frame, FORMING_T, bar)
        assert len(out) == 60  # 59 completed + forming replaced the tail row
        assert float(out.iloc[-1]["open"]) == 1.0


class TestConvergence:
    def test_provisional_equals_committed_at_close(self) -> None:
        """THE pinned invariant: the provisional score on the
        forming-appended window is EXACTLY the committed score once that
        bar closes — same frame, same frozen engine, integer-equal."""
        frame = choppy()
        completed = frame.iloc[:-1]
        last = frame.iloc[-1]
        bar = {"open": float(last["open"]), "high": float(last["high"]),
               "low": float(last["low"]), "close": float(last["close"]),
               "volume": int(last["volume"])}
        provisional_window = append_forming(completed, frame.index[-1], bar)

        committed_result = score_signal(frame, timeframe="5m", min_confidence=0)
        provisional_result = score_signal(
            provisional_window, timeframe="5m", min_confidence=0)

        assert committed_result is not None  # canary: the fixture must fire
        assert provisional_result is not None
        assert provisional_window.equals(frame)
        assert provisional_result.confidence_pct == committed_result.confidence_pct
        assert provisional_result.direction == committed_result.direction
        # pin the fixture's deterministic verdict so silent engine drift bites
        assert (committed_result.direction, committed_result.confidence_pct) == ("SELL", 43)


# ── Hot set ───────────────────────────────────────────────────────────────────


@pytest.fixture
def alert_stream(monkeypatch) -> str:
    stream = f"alerts:test:{uuid.uuid4().hex}"
    monkeypatch.setattr(settings, "live_alert_stream", stream)
    yield stream
    r = redis_sync.from_url(settings.redis_url, decode_responses=True)
    r.delete(stream)
    r.close()


class TestHotSet:
    @pytest.mark.asyncio
    async def test_sources_and_signal_pairs(self, db, sync_redis, alert_stream) -> None:
        sig_stock = await make_stock(db, symbol="HOTSIG")
        trig_stock = await make_stock(db, symbol="HOTTRG")
        watch_stock = await make_stock(db, symbol="HOTWCH")
        await make_stock(db, symbol="HOTCLD")  # cold — must not appear
        signal = await _seed_signal(db, sig_stock.id, profile_key="rrbo")

        sync_redis.xadd(alert_stream, {"sid": trig_stock.id,
                                       "ts": int(NOW.timestamp()) - 10})
        sync_redis.xadd(alert_stream, {"sid": watch_stock.id,  # too old
                                       "ts": int(NOW.timestamp()) - 100_000})

        user = await create_test_user(db, email="hotset@test.com")
        wl = Watchlist(user_id=user.id, name="hot")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        hot, pairs = await load_hot_set(db, sync_redis, NOW)

        assert hot[sig_stock.id].sources == {"signal"}
        assert hot[trig_stock.id].sources == {"trigger"}
        assert hot[watch_stock.id].sources == {"watchlist"}
        assert len(hot) == 3
        assert [(p.stock_id, p.profile_key, p.signal_id) for p in pairs] == [
            (sig_stock.id, "rrbo", str(signal.id))
        ]

    @pytest.mark.asyncio
    async def test_trigger_read_pages_past_500_entry_bursts(
        self, db, sync_redis, alert_stream
    ) -> None:
        """bug-hunter LOW (2026-07-19): one capped XREVRANGE call read only
        the newest 500 entries — an open-auction burst silently shrank the
        configured recency window. The read must PAGE until past the cutoff."""
        target = await make_stock(db, symbol="PAGEDTRG")
        filler = await make_stock(db, symbol="PAGEFILL")
        ts = int(NOW.timestamp()) - 5
        # target's ONLY alert lands first (oldest), then a 550-entry burst
        # pushes it beyond the newest-500 window
        sync_redis.xadd(alert_stream, {"sid": target.id, "ts": ts})
        for _ in range(550):
            sync_redis.xadd(alert_stream, {"sid": filler.id, "ts": ts})

        hot, _pairs = await load_hot_set(db, sync_redis, NOW)

        assert target.id in hot, "in-window entry beyond the newest 500 was dropped"
        assert hot[target.id].sources == {"trigger"}

    @pytest.mark.asyncio
    async def test_clip_priority_signal_over_trigger_over_watchlist(
        self, db, sync_redis, alert_stream, monkeypatch, caplog
    ) -> None:
        monkeypatch.setattr(settings, "live_provisional_hotset_max", 2)
        sig_stock = await make_stock(db, symbol="CLPSIG")
        trig_stock = await make_stock(db, symbol="CLPTRG")
        watch_stock = await make_stock(db, symbol="CLPWCH")
        await _seed_signal(db, sig_stock.id)
        sync_redis.xadd(alert_stream, {"sid": trig_stock.id,
                                       "ts": int(NOW.timestamp()) - 5})
        user = await create_test_user(db, email="clip@test.com")
        wl = Watchlist(user_id=user.id, name="clip")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        with caplog.at_level("WARNING"):
            hot, _pairs = await load_hot_set(db, sync_redis, NOW)

        assert set(hot) == {sig_stock.id, trig_stock.id}  # watchlist clipped
        assert any("hot set clipped" in r.message for r in caplog.records)


# ── Publish ───────────────────────────────────────────────────────────────────


def _row(sid: int, style: str, conf: int | None, signal_id: str | None = None) -> dict:
    return {"provisional": True, "stock_id": sid, "symbol": f"S{sid}",
            "profile_key": None, "style": style, "tf": "5m",
            "confidence": conf, "direction": "BUY" if conf else None,
            "gate": conf is not None, "sources": ["watchlist"],
            **({"signal_id": signal_id} if signal_id else {})}


class TestPublishLeaderboards:
    def test_set_ttl_ordering_and_channel(self, sync_redis) -> None:
        style = "swing"
        pubsub = sync_redis.pubsub()
        pubsub.subscribe(LEADERBOARD_CHANNEL.format(style=style))
        pubsub.get_message(timeout=2)  # consume the subscribe ack

        rows = [_row(1, style, 71), _row(2, style, 88), _row(3, style, None)]
        n = publish_leaderboards(sync_redis, rows, NOW)
        # every known style publishes every cycle (empty boards included)
        assert n == len(ALL_PROVISIONAL_STYLES)

        raw = sync_redis.get(LEADERBOARD_KEY.format(style=style))
        payload = json.loads(raw)
        assert payload["provisional"] is True
        assert payload["style"] == style
        assert [r["confidence"] for r in payload["rows"]] == [88, 71, None]
        ttl = sync_redis.ttl(LEADERBOARD_KEY.format(style=style))
        assert 0 < ttl <= settings.live_provisional_key_ttl_s

        msg = pubsub.get_message(timeout=2)
        assert msg is not None and json.loads(msg["data"])["style"] == style
        pubsub.close()

    def test_top_n_clip_never_drops_signal_rows(self, sync_redis, monkeypatch) -> None:
        monkeypatch.setattr(settings, "live_provisional_top_n", 2)
        rows = [_row(1, "intraday", 90), _row(2, "intraday", 80),
                _row(3, "intraday", 70), _row(4, "intraday", None, signal_id="42")]
        publish_leaderboards(sync_redis, rows, NOW)
        payload = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="intraday")))
        got = [(r["stock_id"], r["confidence"]) for r in payload["rows"]]
        assert got == [(1, 90), (2, 80), (4, None)]  # 3 clipped, signal row kept

    def test_emptied_style_republishes_empty(self, sync_redis) -> None:
        """bug-hunter MEDIUM (2026-07-19, executed repro): a style whose
        rows drop to zero must OVERWRITE its key and tell subscribers —
        the stale board must not outlive the setup behind a 'Live' badge."""
        style = "intraday"
        pubsub = sync_redis.pubsub()
        pubsub.subscribe(LEADERBOARD_CHANNEL.format(style=style))
        pubsub.get_message(timeout=2)

        publish_leaderboards(sync_redis, [_row(1, style, 72)], NOW)
        assert pubsub.get_message(timeout=2) is not None  # cycle 1 frame

        later = NOW + timedelta(seconds=3)
        publish_leaderboards(sync_redis, [], later)  # everything below gate

        payload = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style=style)))
        assert payload["rows"] == []  # old conf-72 row is GONE
        assert payload["as_of"] == later.isoformat()
        msg = pubsub.get_message(timeout=2)
        assert msg is not None, "subscribers must learn the board emptied"
        assert json.loads(msg["data"])["rows"] == []
        pubsub.close()


# ── score_pair 1d path ────────────────────────────────────────────────────────


class TestScorePair1d:
    @pytest.mark.asyncio
    async def test_daily_pair_scores_session_aggregate(self, db) -> None:
        """1d preview = 1d history + today's session-aggregated forming
        bar; must equal score_signal on the manually-assembled frame."""
        stock = await make_stock(db, symbol="DAILY1D")
        frame = choppy(n=100, end=datetime(2026, 7, 15, tzinfo=UTC))
        frame.index = pd.DatetimeIndex(
            [datetime(2026, 7, 15, tzinfo=UTC) - timedelta(days=99 - i)
             for i in range(100)])
        for t, row in frame.iterrows():
            await db.execute(
                text("INSERT INTO ohlcv_1d (time, stock_id, open, high, low,"
                     " close, volume, is_complete)"
                     " VALUES (:t, :sid, :o, :h, :l, :c, :v, true)"),
                {"t": t, "sid": stock.id,
                 "o": Decimal(f"{row['open']:.4f}"), "h": Decimal(f"{row['high']:.4f}"),
                 "l": Decimal(f"{row['low']:.4f}"), "c": Decimal(f"{row['close']:.4f}"),
                 "v": int(row["volume"])},
            )
        await db.commit()

        committed_today = {"open": 100.0, "high": 102.0, "low": 99.5,
                           "close": 101.0, "volume": 40_000,
                           "last_time": datetime(2026, 7, 16, 5, 55, tzinfo=UTC)}
        forming_5m = {"time": int(FORMING_T.timestamp()), "open": 101_0000,
                      "high": 103_0000, "low": 100_8000, "close": 102_5000,
                      "volume": 2_000}

        result, had_data = await score_pair(
            db, stock_id=stock.id, timeframe="1d", min_confidence=0,
            weight_multipliers=None,
            forming_by_tf={(stock.id, 5): forming_5m},
            agg_5m={stock.id: committed_today}, session_day=DAY,
            flows=(Decimal("0"), Decimal("0")), block_net=Decimal("0"),
        )
        assert had_data is True

        expected_bar = {"open": 100.0, "high": 103.0, "low": 99.5,
                        "close": 102.5, "volume": 42_000}
        expected_window = append_forming(
            frame, datetime(2026, 7, 16, tzinfo=UTC), expected_bar)
        expected = score_signal(expected_window, timeframe="1d", min_confidence=0)

        assert expected is not None
        assert result is not None
        assert (result.direction, result.confidence_pct) == (
            expected.direction, expected.confidence_pct)


# ── run_cycle end-to-end (real LiveBook, real DB, real Redis) ────────────────


class TestRunCycleEndToEnd:
    @pytest.mark.asyncio
    async def test_leaderboard_row_matches_direct_engine_score(
        self, db, sync_redis, alert_stream
    ) -> None:
        import tradecore

        frame = rollover_marubozu()
        stock = await make_stock(db, symbol="CYCLE5M")
        await _seed_5m(db, stock.id, frame.iloc[:-1])  # 119 committed
        await make_profile(db, key="prov_intraday", style="intraday",
                           timeframe="5m", schedule="intraday_5m",
                           min_confidence=70, status="active")
        user = await create_test_user(db, email="cycle@test.com")
        wl = Watchlist(user_id=user.id, name="cycle")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=stock.id))
        await db.commit()

        # Rebuild bar 119 tick-by-tick inside the real engine: O→H→L→C.
        last = frame.iloc[-1]
        book = tradecore.LiveBook(int(OPEN_UTC.timestamp()),
                                  int(CLOSE_UTC.timestamp()), [1, 5, 15, 60])
        book.ensure_instruments([stock.id])
        base_ts = int(FORMING_T.timestamp())
        vol = int(last["volume"])
        book.on_ticks([
            (stock.id, base_ts + 5, f"{last['open']:.4f}", None, vol - 3),
            (stock.id, base_ts + 20, f"{last['high']:.4f}", None, 1),
            (stock.id, base_ts + 40, f"{last['low']:.4f}", None, 1),
            (stock.id, base_ts + 60, f"{last['close']:.4f}", None, 1),
        ])

        stats = await run_cycle(db, sync_redis, book, NOW)

        assert stats["hot"] == 1
        raw = sync_redis.get(LEADERBOARD_KEY.format(style="intraday"))
        assert raw is not None, "leaderboard key missing after cycle"
        payload = json.loads(raw)
        rows = payload["rows"]
        assert len(rows) == 1
        row = rows[0]

        expected = score_signal(frame, timeframe="5m", min_confidence=70)
        assert expected is not None
        assert row["provisional"] is True
        assert row["stock_id"] == stock.id
        assert row["symbol"] == "CYCLE5M"
        assert row["profile_key"] == "prov_intraday"
        assert row["tf"] == "5m"
        assert row["gate"] is True
        assert row["sources"] == ["watchlist"]
        assert (row["direction"], row["confidence"]) == (
            expected.direction, expected.confidence_pct)

    @pytest.mark.asyncio
    async def test_active_signal_below_gate_still_publishes(
        self, db, sync_redis, alert_stream
    ) -> None:
        """Active-signal pairs always publish: confidence None = 'your
        signal's setup no longer passes its gate' (the pinned preview)."""
        stock = await make_stock(db, symbol="SIGFLAT")
        for i in range(60):
            await db.execute(
                text("INSERT INTO ohlcv_1h (time, stock_id, open, high, low,"
                     " close, volume, is_complete)"
                     " VALUES (:t, :sid, 100, 100, 100, 100, 1000, true)"),
                {"t": FORMING_T - timedelta(hours=60 - i), "sid": stock.id},
            )
        await db.commit()
        signal = await _seed_signal(db, stock.id, classification="swing",
                                    timeframe="1h", profile_key=None)

        class EmptyBook:
            def forming_snapshot(self, ids: list[int]) -> list[dict]:
                return []

        stats = await run_cycle(db, sync_redis, EmptyBook(), NOW)

        assert stats["rows"] == 1
        payload = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="swing")))
        row = payload["rows"][0]
        assert row["signal_id"] == str(signal.id)
        assert row["confidence"] is None
        assert row["gate"] is False  # a REAL below-gate verdict (data existed)
        assert row["style"] == "swing"

    @pytest.mark.asyncio
    async def test_signal_with_no_window_publishes_gate_none(
        self, db, sync_redis, alert_stream
    ) -> None:
        """No candles at all: the row must say 'no data' (gate=None) —
        never a below-gate verdict about a live position's setup."""
        stock = await make_stock(db, symbol="SIGNODAT")
        signal = await _seed_signal(db, stock.id, classification="swing",
                                    timeframe="1h", profile_key=None)

        class EmptyBook:
            def forming_snapshot(self, ids: list[int]) -> list[dict]:
                return []

        await run_cycle(db, sync_redis, EmptyBook(), NOW)

        payload = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="swing")))
        row = payload["rows"][0]
        assert row["signal_id"] == str(signal.id)
        assert row["gate"] is None
        assert row["confidence"] is None

    @pytest.mark.asyncio
    async def test_signal_pair_binds_inactive_profile_params(
        self, db, sync_redis, alert_stream
    ) -> None:
        """quant-verifier HIGH (2026-07-18): a signal whose profile was
        deactivated must STILL score with that profile's params — style,
        timeframe, gate — not fall back to legacy defaults."""
        stock = await make_stock(db, symbol="SIGINACT")
        frame = rollover_marubozu()
        await _seed_5m(db, stock.id, frame)  # all 120 committed (no forming here)
        await make_profile(db, key="parked_fno", style="fno",
                           timeframe="5m", schedule="intraday_5m",
                           min_confidence=70, status="inactive")
        signal = await _seed_signal(db, stock.id, classification="swing",
                                    timeframe="1h", profile_key="parked_fno")

        class EmptyBook:
            def forming_snapshot(self, ids: list[int]) -> list[dict]:
                return []

        await run_cycle(db, sync_redis, EmptyBook(), NOW)

        # On the OLD code this row lands on the legacy shelf: style="swing"
        # (classification), tf="1h", scored against 60 flat 1h bars.
        raw = sync_redis.get(LEADERBOARD_KEY.format(style="fno"))
        assert raw is not None, "row must publish under the BOUND profile's style"
        row = json.loads(raw)["rows"][0]
        assert row["signal_id"] == str(signal.id)
        assert row["tf"] == "5m"
        expected = score_signal(frame, timeframe="5m", min_confidence=70)
        assert expected is not None
        assert (row["direction"], row["confidence"]) == (
            expected.direction, expected.confidence_pct)


# ── Thread lifecycle ──────────────────────────────────────────────────────────


class TestRefresherThread:
    def test_run_provisional_stops_cleanly(self) -> None:
        """The worker joins this thread on shutdown: a set stop event must
        end the loop and dispose the engine/redis/loop without raising."""
        import threading

        from app.broker.provisional import run_provisional

        class NeverBook:
            def forming_snapshot(self, ids: list[int]) -> list[dict]:
                raise AssertionError("no cycle may run after stop is set")

        stop = threading.Event()
        stop.set()
        t = threading.Thread(target=run_provisional, args=(NeverBook(), stop))
        t.start()
        t.join(timeout=10)
        assert not t.is_alive()


# ── REST reconciliation ───────────────────────────────────────────────────────


class TestProvisionalRest:
    @pytest.mark.asyncio
    async def test_get_leaderboard_roundtrip(self, db, client, sync_redis) -> None:
        from tests.helpers import get_auth_headers

        await create_test_user(db, email="prov-rest@test.com")
        headers = await get_auth_headers(client, email="prov-rest@test.com")

        publish_leaderboards(sync_redis, [_row(7, "fno", 81)], NOW)
        resp = await client.get("/api/v1/market/provisional/fno", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["provisional"] is True
        assert body["style"] == "fno"
        assert body["rows"][0]["stock_id"] == 7
        assert body["rows"][0]["confidence"] == 81

        resp = await client.get("/api/v1/market/provisional/investment",
                                headers=headers)
        assert resp.status_code == 200
        assert resp.json()["rows"] == []  # empty state, never an error

        resp = await client.get("/api/v1/market/provisional/bogus", headers=headers)
        assert resp.status_code == 404
