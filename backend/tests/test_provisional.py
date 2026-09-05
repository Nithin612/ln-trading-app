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
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
import redis as redis_sync
from app.broker.provisional import (
    ALL_PROVISIONAL_STYLES,
    HEALTH_KEY,
    LEADERBOARD_CHANNEL,
    LEADERBOARD_KEY,
    HotStock,
    _in_session,
    _seed_counters,
    append_forming,
    apply_hotset_cap,
    forming_daily_bar,
    load_hot_set,
    publish_cycle_stats,
    publish_leaderboards,
    read_cycle_stats,
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

        sync_redis.xadd(alert_stream, {"sid": trig_stock.id, "style": "intraday",
                                       "ts": int(NOW.timestamp()) - 10})
        sync_redis.xadd(alert_stream, {"sid": watch_stock.id,  # too old
                                       "style": "intraday",
                                       "ts": int(NOW.timestamp()) - 100_000})

        user = await create_test_user(db, email="hotset@test.com")
        wl = Watchlist(user_id=user.id, name="hot")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        hot, pairs, hot_stats = await load_hot_set(db, sync_redis, NOW)

        assert (hot_stats.raw, hot_stats.kept, hot_stats.clipped) == (3, 3, 0)
        assert (hot_stats.signal, hot_stats.trigger, hot_stats.watchlist) == (1, 1, 1)
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
        sync_redis.xadd(alert_stream, {"sid": target.id, "style": "swing", "ts": ts})
        for _ in range(550):
            sync_redis.xadd(alert_stream, {"sid": filler.id, "style": "swing", "ts": ts})

        hot, _pairs, _stats = await load_hot_set(db, sync_redis, NOW)

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
        sync_redis.xadd(alert_stream, {"sid": trig_stock.id, "style": "intraday",
                                       "ts": int(NOW.timestamp()) - 5})
        user = await create_test_user(db, email="clip@test.com")
        wl = Watchlist(user_id=user.id, name="clip")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        with caplog.at_level("WARNING"):
            hot, _pairs, hot_stats = await load_hot_set(db, sync_redis, NOW)

        assert set(hot) == {sig_stock.id, trig_stock.id}  # watchlist clipped
        assert any("hot set clipped" in r.message for r in caplog.records)
        # the clip must be TRENDABLE, not log-only (that is what made the
        # 2026-08-18 flood invisible to everything but a terminal)
        assert (hot_stats.raw, hot_stats.kept, hot_stats.clipped) == (3, 2, 1)
        assert hot_stats.watchlist == 0

    # ── breadth-alert flood (root cause of the 2026-08-18 clip storm) ────────

    @pytest.mark.asyncio
    async def test_market_breadth_alerts_never_reach_the_hot_set(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        """REGRESSION 2026-08-18: `_recent_trigger_sids` admitted EVERY alert
        regardless of tag, so market-breadth levels (vburst on 1271 distinct
        stocks in a 15-min window, plus PDH/PDL) flooded the hot set. The cap
        then went to the lowest stock_ids and the watchlist — a documented
        hot-set source — was never scored at all."""
        monkeypatch.setattr(settings, "live_provisional_hotset_max", 3)
        ts = int(NOW.timestamp()) - 5
        burst = [await make_stock(db, symbol=f"VBRST{i}") for i in range(5)]
        for st in burst:
            sync_redis.xadd(alert_stream, {"sid": st.id, "tag": "volume_burst",
                                           "source": "vburst", "style": "market",
                                           "ts": ts})
        watch_stock = await make_stock(db, symbol="WLSURV")
        user = await create_test_user(db, email="breadth@test.com")
        wl = Watchlist(user_id=user.id, name="breadth")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        hot, _pairs, hot_stats = await load_hot_set(db, sync_redis, NOW)

        # CANARY: on the old code the 5 breadth stocks outranked watchlist
        # (trigger beats watchlist) and clipped it out at cap=3.
        assert set(hot) == {watch_stock.id}
        assert not any(st.id in hot for st in burst)
        assert (hot_stats.raw, hot_stats.clipped, hot_stats.trigger) == (1, 0, 0)

    @pytest.mark.asyncio
    async def test_signal_bound_alert_is_still_a_trigger(
        self, db, sync_redis, alert_stream
    ) -> None:
        """The filter is on BREADTH, not on the trigger source itself:
        entry-zone / SL / TP alerts carry the signal's classification as
        style and must keep priming the hot set."""
        ts = int(NOW.timestamp()) - 5
        zone = await make_stock(db, symbol="ZONEHOT")
        sync_redis.xadd(alert_stream, {"sid": zone.id, "tag": "zone_enter",
                                       "source": "entry_zone", "style": "swing",
                                       "signal_id": str(uuid.uuid4()), "ts": ts})

        hot, _pairs, _stats = await load_hot_set(db, sync_redis, NOW)

        assert hot[zone.id].sources == {"trigger"}

    @pytest.mark.asyncio
    async def test_style_less_alert_reads_as_market_fail_closed(
        self, db, sync_redis, alert_stream
    ) -> None:
        """An entry with no `style` predates the stamp. The producer's own
        default is "market" (`live_worker`: meta.get("style", "market")), so
        it must fail CLOSED — failing open would let the flood back in
        silently the moment an alert shape changed."""
        orphan = await make_stock(db, symbol="NOSTYLE")
        sync_redis.xadd(alert_stream, {"sid": orphan.id,
                                       "ts": int(NOW.timestamp()) - 5})

        hot, _pairs, _stats = await load_hot_set(db, sync_redis, NOW)

        assert orphan.id not in hot

    @pytest.mark.asyncio
    async def test_market_max_dials_breadth_back_newest_first(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        """The dial back: >0 admits that many market-level stocks, and
        recency decides which (the stream is read newest-first). Recency is
        stream-ID order, not the `ts` field."""
        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 1)
        ts = int(NOW.timestamp()) - 5
        older = await make_stock(db, symbol="MKTOLD")
        newer = await make_stock(db, symbol="MKTNEW")
        sync_redis.xadd(alert_stream, {"sid": older.id, "style": "market", "ts": ts})
        sync_redis.xadd(alert_stream, {"sid": newer.id, "style": "market", "ts": ts})

        hot, _pairs, stats = await load_hot_set(db, sync_redis, NOW)

        assert newer.id in hot, "newest market-level alert was not admitted"
        assert older.id not in hot, "market admission is not bounded"
        assert hot[newer.id].sources == {"market"}, "breadth must not read as trigger"
        assert (stats.market, stats.trigger) == (1, 0)

    @pytest.mark.asyncio
    async def test_market_recency_survives_a_page_boundary(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        """The market tier is ordered by the PAGED read, so page-2 recency
        needs its own cover: the newest entry must still win after a >500
        entry burst pushes it off page 1 (quant-verifier INFO 2026-08-19)."""
        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 1)
        ts = int(NOW.timestamp()) - 5
        newest = await make_stock(db, symbol="MKTPG1")
        buried = await make_stock(db, symbol="MKTPG2")
        sync_redis.xadd(alert_stream, {"sid": buried.id, "style": "market", "ts": ts})
        sync_redis.xadd(alert_stream, {"sid": newest.id, "style": "market", "ts": ts})
        for _ in range(550):  # burst pushes BOTH beyond the newest 500
            sync_redis.xadd(alert_stream, {"sid": newest.id, "style": "market", "ts": ts})

        hot, _pairs, _stats = await load_hot_set(db, sync_redis, NOW)

        assert newest.id in hot
        assert buried.id not in hot, "page-2 ordering lost: the older sid won"

    @pytest.mark.asyncio
    async def test_a_market_slot_must_buy_new_coverage(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        """REGRESSION (quant-verifier MEDIUM 2026-08-19): the market list was
        deduped only against signal-bound alert sids, so a slot could be spent
        on a stock the signal/watchlist sources had ALREADY made hot — or on
        an inactive stock, since is_active was filtered after the trim. Either
        way the dial silently delivered less than it claimed."""
        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 1)
        ts = int(NOW.timestamp()) - 5
        signalled = await make_stock(db, symbol="MKTDUPE")
        fresh = await make_stock(db, symbol="MKTFRESH")
        await _seed_signal(db, signalled.id)
        # the ALREADY-HOT stock is newest, so a naive dial spends its only
        # slot on it and admits nothing new
        sync_redis.xadd(alert_stream, {"sid": fresh.id, "style": "market", "ts": ts})
        sync_redis.xadd(alert_stream, {"sid": signalled.id, "style": "market", "ts": ts})

        hot, _pairs, stats = await load_hot_set(db, sync_redis, NOW)

        assert fresh.id in hot, "the slot was wasted on an already-hot stock"
        assert hot[signalled.id].sources == {"signal"}
        assert stats.market == 1

    @pytest.mark.asyncio
    async def test_inactive_stock_never_eats_a_market_slot(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 1)
        ts = int(NOW.timestamp()) - 5
        dead = await make_stock(db, symbol="MKTDEAD")
        live = await make_stock(db, symbol="MKTLIVE")
        dead.is_active = False
        await db.commit()
        sync_redis.xadd(alert_stream, {"sid": live.id, "style": "market", "ts": ts})
        sync_redis.xadd(alert_stream, {"sid": dead.id, "style": "market", "ts": ts})

        hot, _pairs, _stats = await load_hot_set(db, sync_redis, NOW)

        assert live.id in hot, "an inactive stock consumed the only slot"
        assert dead.id not in hot

    @pytest.mark.asyncio
    async def test_a_dead_alert_stream_fails_open_not_crashing(
        self, db, sync_redis, monkeypatch
    ) -> None:
        """REGRESSION (mypy strict, 2026-08-19): splitting the alert read into
        a (signal_bound, market) tuple left the read-failure path returning a
        bare `set()`, so the very path meant to fail OPEN would instead raise
        on tuple-unpacking and take the whole cycle down. The hot set must
        still assemble from the DB sources alone."""

        class DeadStream:
            def xrevrange(self, *args, **kwargs):
                raise RuntimeError("redis down")

        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 5)
        watch_stock = await make_stock(db, symbol="FAILOPEN")
        user = await create_test_user(db, email="failopen@test.com")
        wl = Watchlist(user_id=user.id, name="failopen")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        hot, _pairs, stats = await load_hot_set(db, DeadStream(), NOW)

        assert set(hot) == {watch_stock.id}, "a dead stream must not empty the hot set"
        assert (stats.trigger, stats.market) == (0, 0)

    @pytest.mark.asyncio
    async def test_market_tier_can_never_clip_the_watchlist(
        self, db, sync_redis, alert_stream, monkeypatch
    ) -> None:
        """The original bug in miniature: breadth admitted at TRIGGER priority
        outranked the watchlist and starved it. The discovery tier therefore
        ranks BELOW watchlist — turning the dial on must never cost coverage
        the user explicitly asked for."""
        monkeypatch.setattr(settings, "live_provisional_hotset_max", 1)
        monkeypatch.setattr(settings, "live_provisional_trigger_market_max", 5)
        ts = int(NOW.timestamp()) - 5
        watch_stock = await make_stock(db, symbol="WLKEEP")
        for i in range(3):
            mkt = await make_stock(db, symbol=f"MKTPUSH{i}")
            sync_redis.xadd(alert_stream, {"sid": mkt.id, "style": "market", "ts": ts})
        user = await create_test_user(db, email="mktrank@test.com")
        wl = Watchlist(user_id=user.id, name="rank")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=watch_stock.id))
        await db.commit()

        hot, _pairs, stats = await load_hot_set(db, sync_redis, NOW)

        assert set(hot) == {watch_stock.id}, "breadth outranked the watchlist again"
        assert (stats.watchlist, stats.market) == (1, 0)


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


class TestCycleHealth:
    """Cycle health has to be readable AFTER the session: `make live-worker`
    writes no log file (only `make soak` tees one), so a run's cadence/clip
    record lived only in a terminal. Cumulative + per-day, so the answer is
    a RATE over a day and it survives a mid-session restart."""

    DAY = "2026-08-19"

    def _publish(self, redis, **over):
        kwargs = dict(
            day=self.DAY, now_utc=NOW, cadence_s=3.0, cycles=4, overruns=1,
            clip_cycles=2, elapsed_ms=4200.0, elapsed_sum_ms=12_000.0,
            elapsed_max_ms=4200.0, restarts=0, seed_failed=False,
            stats={"hot": 120, "clipped": 0},
        )
        kwargs.update(over)
        publish_cycle_stats(redis, **kwargs)

    def test_cumulative_rates_and_ttl(self, sync_redis) -> None:
        self._publish(sync_redis)

        raw = sync_redis.get(HEALTH_KEY.format(day=self.DAY))
        assert raw is not None, "cycle-health key missing"
        doc = json.loads(raw)
        assert (doc["cycles"], doc["overruns"], doc["clip_cycles"]) == (4, 1, 2)
        assert doc["overrun_pct"] == 25.0
        assert doc["clip_pct"] == 50.0
        assert doc["elapsed_mean_ms"] == 3000.0
        assert doc["elapsed_max_ms"] == 4200.0
        assert doc["cadence_ms"] == 3000.0
        assert doc["last"] == {"hot": 120, "clipped": 0}
        assert (doc["day"], doc["as_of"]) == (self.DAY, NOW.isoformat())
        # a week: "monitor it for a few days" with no scheduler running
        ttl = sync_redis.ttl(HEALTH_KEY.format(day=self.DAY))
        assert 0 < ttl <= settings.live_provisional_health_ttl_s
        assert settings.live_provisional_health_ttl_s >= 7 * 86_400

    def test_zero_cycles_never_divides_by_zero(self, sync_redis) -> None:
        self._publish(sync_redis, cycles=0, overruns=0, clip_cycles=2,
                      elapsed_sum_ms=0.0)

        doc = json.loads(sync_redis.get(HEALTH_KEY.format(day=self.DAY)))
        assert (doc["overrun_pct"], doc["clip_pct"], doc["elapsed_mean_ms"]) == (
            0.0, 0.0, 0.0,
        )

    def test_redis_failure_never_disturbs_the_cycle(self) -> None:
        class Boom:
            def set(self, *args, **kwargs):
                raise RuntimeError("redis down")

        self._publish(Boom())  # must not raise — monitoring is not the job

    def test_restart_resumes_the_days_counters(self, sync_redis) -> None:
        """The supervisor restarts the worker mid-session (token expiry is a
        normal lifecycle event). Re-seeding from the day's key is what keeps
        a restart from zeroing the day's record — and elapsed_sum is
        reconstructed as mean × n, since only the mean is stored."""
        self._publish(sync_redis, cycles=4, overruns=1, clip_cycles=2,
                      elapsed_sum_ms=12_000.0, elapsed_max_ms=4200.0)

        prior = read_cycle_stats(sync_redis, self.DAY)

        assert prior is not None
        assert (prior["cycles"], prior["overruns"], prior["clip_cycles"]) == (4, 1, 2)
        assert prior["elapsed_mean_ms"] * prior["cycles"] == 12_000.0
        assert prior["restarts"] == 0

    def test_read_is_none_when_nothing_recorded_or_junk(self, sync_redis) -> None:
        assert read_cycle_stats(sync_redis, "1999-01-01") is None
        sync_redis.set(HEALTH_KEY.format(day="1999-01-02"), "not json")
        assert read_cycle_stats(sync_redis, "1999-01-02") is None
        sync_redis.set(HEALTH_KEY.format(day="1999-01-03"), "[1,2]")
        assert read_cycle_stats(sync_redis, "1999-01-03") is None, "list is not a doc"

    def test_read_failure_is_not_fatal(self) -> None:
        class Boom:
            def get(self, *args, **kwargs):
                raise RuntimeError("redis down")

        assert read_cycle_stats(Boom(), self.DAY) is None

    def test_seed_failure_is_stamped_on_the_key(self, sync_redis) -> None:
        """A WIPED day must not read as a first run. Without the flag the two
        are identical — `restarts` re-seeds to 0 as well — and the key exists
        precisely because there is no log file to cross-check."""
        self._publish(sync_redis, seed_failed=True)

        doc = json.loads(sync_redis.get(HEALTH_KEY.format(day=self.DAY)))
        assert doc["seed_failed"] is True

    def test_publish_survives_an_unserialisable_stats_dict(self, sync_redis) -> None:
        """`json.dumps` now sits INSIDE the guard: the docstring's promise that
        publishing can never disturb a cycle held only while `run_cycle`
        returned an all-int dict (bug-hunter LOW 2026-08-19, latent)."""
        self._publish(sync_redis, stats={"hot": object()})  # must not raise


class TestSeedCounters:
    """Resuming the day's counters must never stop the thread from starting.
    `run_provisional` is a NON-JOINED daemon thread with no restart path, so
    an exception here takes the provisional layer dark for the whole session
    (bug-hunter LOW 2026-08-19, reproduced)."""

    DAY = "2026-08-19"

    def test_resumes_and_counts_the_restart(self, sync_redis) -> None:
        publish_cycle_stats(
            sync_redis, day=self.DAY, now_utc=NOW, cadence_s=3.0, cycles=4,
            overruns=1, clip_cycles=2, elapsed_ms=3000.0, elapsed_sum_ms=12_000.0,
            elapsed_max_ms=4200.0, restarts=0, seed_failed=False, stats={},
        )

        cycles, overruns, clips, sum_ms, max_ms, restarts, failed = _seed_counters(
            sync_redis, self.DAY
        )

        assert (cycles, overruns, clips) == (4, 1, 2)
        assert sum_ms == 12_000.0  # mean × n round-trips the sum
        assert max_ms == 4200.0
        assert restarts == 1, "a resumed day is a restart"
        assert failed is False

    def test_absent_key_starts_fresh_without_counting_a_restart(self, sync_redis) -> None:
        assert _seed_counters(sync_redis, "1999-01-01") == (0, 0, 0, 0.0, 0.0, 0, False)

    def test_non_numeric_counters_never_kill_the_thread(self, sync_redis) -> None:
        """CANARY: seeding used to run OUTSIDE the loop's try, so a poisoned
        key (a debugging script writing the same key by hand) raised straight
        out of the thread — dark all session, traceback only on a terminal
        `make live-worker` does not tee."""
        sync_redis.set(
            HEALTH_KEY.format(day=self.DAY),
            json.dumps({"cycles": None, "overruns": 0, "elapsed_mean_ms": "x"}),
        )

        seeded = _seed_counters(sync_redis, self.DAY)

        assert seeded == (0, 0, 0, 0.0, 0.0, 0, True), "poisoned key must fail SAFE"

    def test_junk_payload_starts_fresh(self, sync_redis) -> None:
        sync_redis.set(HEALTH_KEY.format(day=self.DAY), "not json")
        assert _seed_counters(sync_redis, self.DAY) == (0, 0, 0, 0.0, 0.0, 0, False)

    def test_read_failure_is_flagged_not_raised(self) -> None:
        class Boom:
            def get(self, *args, **kwargs):
                raise RuntimeError("redis down")

        cycles, _o, _c, _s, _m, restarts, failed = _seed_counters(Boom(), self.DAY)

        assert (cycles, restarts) == (0, 0)
        assert failed is True, "a Redis blip must be distinguishable from a fresh day"


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


# ── Scoring memo (cycle cost) ─────────────────────────────────────────────────


class TestScoringMemo:
    """A provisional cycle's cost is the frozen engine, not the DB: measured
    2026-08-14 on the live hot set, `run_all_factors` was 45.7 ms/window and
    92.6% of a 15 s cycle against a 3 s cadence, because every profile
    scoring a stock re-ran it from scratch (five 1d profiles → five runs).

    The memo collapses work whose inputs are byte-identical — the frozen
    scorer is pure, so that answer IS the current answer. These tests pin
    the other half: it must NEVER collapse work whose inputs differ."""

    async def _stock_with_forming_open(self, db, symbol: str):
        """119 committed 5m bars + a book holding only the last bar's OPEN
        tick. Returns (stock, frame, book, base_ts, vol)."""
        import tradecore

        frame = rollover_marubozu()
        stock = await make_stock(db, symbol=symbol)
        await _seed_5m(db, stock.id, frame.iloc[:-1])
        book = tradecore.LiveBook(
            int(OPEN_UTC.timestamp()), int(CLOSE_UTC.timestamp()), [1, 5, 15, 60]
        )
        book.ensure_instruments([stock.id])
        last = frame.iloc[-1]
        base_ts = int(FORMING_T.timestamp())
        vol = int(last["volume"])
        book.on_ticks([(stock.id, base_ts + 5, f"{last['open']:.4f}", None, vol - 3)])
        return stock, frame, book, base_ts, vol

    def _finish_marubozu(self, book, sid: int, frame, base_ts: int) -> None:
        last = frame.iloc[-1]
        book.on_ticks([
            (sid, base_ts + 20, f"{last['high']:.4f}", None, 1),
            (sid, base_ts + 40, f"{last['low']:.4f}", None, 1),
            (sid, base_ts + 60, f"{last['close']:.4f}", None, 1),
        ])

    @pytest.mark.asyncio
    async def test_profiles_sharing_params_score_once(
        self, db, sync_redis, alert_stream
    ) -> None:
        """Two profiles, same (timeframe, gate, multipliers), same stock:
        two published rows off ONE engine call and ONE window load."""
        stock, frame, book, base_ts, _vol = await self._stock_with_forming_open(
            db, "MEMOSHARE"
        )
        self._finish_marubozu(book, stock.id, frame, base_ts)
        for key, style in (("memo_a", "intraday"), ("memo_b", "fno")):
            await make_profile(db, key=key, style=style, timeframe="5m",
                               schedule="intraday_5m", min_confidence=70,
                               status="active")
        user = await create_test_user(db, email="memoshare@test.com")
        wl = Watchlist(user_id=user.id, name="memo")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=stock.id))
        await db.commit()

        stats = await run_cycle(db, sync_redis, book, NOW)

        assert stats["pairs_scored"] == 2
        # On the OLD code both of these were 2: the engine ran per PAIR.
        assert stats["engine_calls"] == 1
        assert stats["memo_hits"] == 1
        assert stats["windows"] == 1

        expected = score_signal(frame, timeframe="5m", min_confidence=70)
        assert expected is not None
        seen = []
        for style in ("intraday", "fno"):
            row = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style=style)))["rows"][0]
            seen.append((row["direction"], row["confidence"]))
        assert seen == [(expected.direction, expected.confidence_pct)] * 2

    @pytest.mark.asyncio
    async def test_unchanged_inputs_reuse_the_memo(
        self, db, sync_redis, alert_stream
    ) -> None:
        """A second cycle over an unmoved book does no engine work — and
        publishes exactly what the first cycle did."""
        stock, frame, book, base_ts, _vol = await self._stock_with_forming_open(
            db, "MEMOSTILL"
        )
        self._finish_marubozu(book, stock.id, frame, base_ts)
        await make_profile(db, key="memo_still", style="fno", timeframe="5m",
                           schedule="intraday_5m", min_confidence=70,
                           status="active")
        await _seed_signal(db, stock.id, classification="swing",
                           timeframe="5m", profile_key="memo_still")

        first = await run_cycle(db, sync_redis, book, NOW)
        row_1 = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"][0]
        second = await run_cycle(db, sync_redis, book, NOW + timedelta(seconds=3))
        row_2 = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"][0]

        assert first["engine_calls"] == 1
        assert second["engine_calls"] == 0
        assert second["memo_hits"] == 1
        assert second["pairs_scored"] == first["pairs_scored"] == 1
        assert (row_2["direction"], row_2["confidence"]) == (
            row_1["direction"], row_1["confidence"])

    @pytest.mark.asyncio
    async def test_changed_forming_bar_rescores(
        self, db, sync_redis, alert_stream
    ) -> None:
        """THE canary: the forming bar is what makes a provisional score
        provisional. A memo that keyed on the stock alone would freeze the
        preview at the first tick of the bar and never move again."""
        stock, frame, book, base_ts, _vol = await self._stock_with_forming_open(
            db, "MEMOMOVE"
        )
        await make_profile(db, key="memo_move", style="fno", timeframe="5m",
                           schedule="intraday_5m", min_confidence=70,
                           status="active")
        await _seed_signal(db, stock.id, classification="swing",
                           timeframe="5m", profile_key="memo_move")

        # Cycle 1: the bar holds only its open tick (flat, no marubozu).
        await run_cycle(db, sync_redis, book, NOW)
        row_1 = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"][0]

        # Cycle 2: the bar completes into the big red marubozu.
        self._finish_marubozu(book, stock.id, frame, base_ts)
        second = await run_cycle(db, sync_redis, book, NOW + timedelta(seconds=3))
        row_2 = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"][0]

        assert second["engine_calls"] == 1, "a moved forming bar must rescore"
        assert second["memo_hits"] == 0
        expected = score_signal(frame, timeframe="5m", min_confidence=70)
        assert expected is not None
        assert (row_2["direction"], row_2["confidence"]) == (
            expected.direction, expected.confidence_pct)
        # Canary: a slot keyed without the forming bar would republish row_1.
        assert (row_1["direction"], row_1["confidence"]) != (
            row_2["direction"], row_2["confidence"])

    @pytest.mark.asyncio
    async def test_differing_gate_never_shares_a_slot(
        self, db, sync_redis, alert_stream
    ) -> None:
        """min_confidence is part of the scorer's input, so it is part of
        the slot: a shared slot would publish one profile's gate verdict
        under the other profile's name."""
        stock, frame, book, base_ts, _vol = await self._stock_with_forming_open(
            db, "MEMOGATE"
        )
        self._finish_marubozu(book, stock.id, frame, base_ts)
        await make_profile(db, key="memo_gate_lo", style="intraday", timeframe="5m",
                           schedule="intraday_5m", min_confidence=70, status="active")
        await make_profile(db, key="memo_gate_hi", style="fno", timeframe="5m",
                           schedule="intraday_5m", min_confidence=95, status="active")
        user = await create_test_user(db, email="memogate@test.com")
        wl = Watchlist(user_id=user.id, name="memogate")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=stock.id))
        await db.commit()

        stats = await run_cycle(db, sync_redis, book, NOW)

        assert stats["engine_calls"] == 2, "different gates are different work"
        assert stats["memo_hits"] == 0
        assert stats["windows"] == 1, "…but they still share one window load"
        # The 95-gate profile rejects what the 70-gate profile publishes.
        assert json.loads(
            sync_redis.get(LEADERBOARD_KEY.format(style="intraday")))["rows"]
        assert json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"] == []

    @pytest.mark.asyncio
    async def test_shared_window_is_not_mutated_by_scoring(self, db) -> None:
        """Window dedup rests on the frozen scorer treating its frame as
        READ-ONLY: with no forming bar the engine is handed the shared
        object itself, so a factor that ever wrote a column into it would
        feed the next profile the previous one's leftovers."""
        frame = rollover_marubozu()
        stock = await make_stock(db, symbol="MEMOPURE")
        await _seed_5m(db, stock.id, frame)

        windows: dict[tuple[int, str], pd.DataFrame] = {}
        kwargs = dict(
            stock_id=stock.id, timeframe="5m", forming_by_tf={}, agg_5m={},
            session_day=DAY, flows=(Decimal("0"), Decimal("0")),
            block_net=Decimal("0"), windows=windows,
        )
        first, _ = await score_pair(db, min_confidence=70,
                                    weight_multipliers=None, **kwargs)
        cached = windows[(stock.id, "5m")]
        snapshot = cached.to_numpy(copy=True)
        columns = list(cached.columns)

        second, _ = await score_pair(db, min_confidence=70,
                                     weight_multipliers={"momentum": 1.5}, **kwargs)

        assert len(windows) == 1, "the second pair must reuse the loaded window"
        assert list(cached.columns) == columns
        assert np.array_equal(cached.to_numpy(), snapshot)
        assert first is not None and second is not None
        # Same window, different multipliers → genuinely independent answers.
        expected = score_signal(frame, timeframe="5m", min_confidence=70)
        assert expected is not None
        assert first.confidence_pct == expected.confidence_pct

    @pytest.mark.asyncio
    async def test_differing_multipliers_never_share_a_slot(
        self, db, sync_redis, alert_stream
    ) -> None:
        """Weight multipliers rescale factor scores before the gate — the
        6.4 retune ships exactly this shape (base vs momentum ×1.5), so a
        slot that ignored them would make an A/B compare against itself."""
        stock, frame, book, base_ts, _vol = await self._stock_with_forming_open(
            db, "MEMOMULT"
        )
        self._finish_marubozu(book, stock.id, frame, base_ts)
        await make_profile(db, key="memo_mult_base", style="intraday", timeframe="5m",
                           schedule="intraday_5m", min_confidence=70, status="active")
        await make_profile(db, key="memo_mult_x15", style="fno", timeframe="5m",
                           schedule="intraday_5m", min_confidence=70, status="active",
                           weight_multipliers={"momentum": 1.5})
        user = await create_test_user(db, email="memomult@test.com")
        wl = Watchlist(user_id=user.id, name="memomult")
        db.add(wl)
        await db.flush()
        db.add(WatchlistItem(watchlist_id=wl.id, stock_id=stock.id))
        await db.commit()

        stats = await run_cycle(db, sync_redis, book, NOW)

        assert stats["engine_calls"] == 2
        assert stats["memo_hits"] == 0
        scaled = score_signal(frame, timeframe="5m", min_confidence=70,
                              weight_multipliers={"momentum": 1.5})
        assert scaled is not None
        row = json.loads(sync_redis.get(LEADERBOARD_KEY.format(style="fno")))["rows"][0]
        assert (row["direction"], row["confidence"]) == (
            scaled.direction, scaled.confidence_pct)


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


# ── A26: the hot-set capacity boundary ──────────────────────────────────────
# The failure this prevents already happened: breadth alerts flooded the hot set,
# watchlist stocks silently stopped being scored, and it was found weeks later. The rule
# is now that the cap is HARD for discovery tiers and SOFT for protected ones — because
# dropping a signal-bound stock does not shed load, it removes a signal from the record.


def _hot(spec: dict[int, str]) -> dict[int, HotStock]:
    """{stock_id: "signal"|"trigger"|"watchlist"|"market"} → a hot set."""
    return {sid: HotStock(symbol=f"S{sid}", sources={src}) for sid, src in spec.items()}


class TestHotSetCap:
    def test_under_the_cap_nothing_is_touched(self) -> None:
        hot = _hot({1: "signal", 2: "watchlist", 3: "market"})
        kept, overflow = apply_hotset_cap(hot, cap=10)
        assert kept == hot
        assert overflow == 0

    def test_discovery_tiers_are_clipped_to_fit(self) -> None:
        hot = _hot({1: "signal", 2: "trigger", 3: "watchlist", 4: "market", 5: "market"})
        kept, overflow = apply_hotset_cap(hot, cap=3)
        assert overflow == 0
        assert len(kept) == 3
        assert {1, 2} <= set(kept), "protected stocks must survive the clip"

    def test_a_signal_bound_stock_is_never_dropped(self) -> None:
        """The Bucket-A property: the cap must not decide which signals exist. With more
        signal-bound stocks than the cap, ALL of them are admitted and the budget is
        knowingly exceeded."""
        hot = _hot({i: "signal" for i in range(1, 11)})
        kept, overflow = apply_hotset_cap(hot, cap=4)
        assert len(kept) == 10, "protected stocks were dropped to satisfy a CPU budget"
        assert overflow == 6
        assert set(kept) == set(hot)

    def test_protected_overflow_drops_every_discovery_stock(self) -> None:
        """When protected work alone exceeds the cap there is no budget left; discovery is
        dropped wholesale rather than partially, so the readout is unambiguous."""
        hot = _hot({1: "signal", 2: "signal", 3: "signal", 8: "watchlist", 9: "market"})
        kept, overflow = apply_hotset_cap(hot, cap=2)
        assert set(kept) == {1, 2, 3}
        assert overflow == 1

    def test_triggers_are_protected_alongside_signals(self) -> None:
        hot = _hot({1: "trigger", 2: "trigger", 3: "watchlist"})
        kept, overflow = apply_hotset_cap(hot, cap=1)
        assert set(kept) == {1, 2}
        assert overflow == 1

    def test_a_multi_source_stock_takes_its_strongest_tier(self) -> None:
        """A stock that is both watchlisted and signal-bound is protected — the weakest
        source must not demote it into the clippable pool."""
        hot = {
            1: HotStock(symbol="S1", sources={"watchlist", "signal"}),
            2: HotStock(symbol="S2", sources={"watchlist"}),
            3: HotStock(symbol="S3", sources={"market"}),
        }
        kept, _overflow = apply_hotset_cap(hot, cap=1)
        assert set(kept) == {1}

    def test_the_overflow_is_reported_not_swallowed(self, caplog: pytest.LogCaptureFixture) -> None:
        """A26's actual demand: refuse LOUDLY at the boundary, with the numbers and a
        remedy. An ERROR-level record naming both is what makes it un-missable."""
        with caplog.at_level(logging.ERROR):
            apply_hotset_cap(_hot({i: "signal" for i in range(1, 8)}), cap=3)
        assert any(r.levelno >= logging.ERROR for r in caplog.records)
        msg = caplog.text
        assert "EXCEEDED" in msg
        assert "REMEDY" in msg
        assert "live_provisional_hotset_max" in msg

    def test_an_ordinary_clip_also_names_a_remedy(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            apply_hotset_cap(
                _hot({1: "signal", 2: "watchlist", 3: "market", 4: "market"}), cap=2
            )
        assert "REMEDY" in caplog.text

    def test_a_nonsense_cap_is_a_no_op_rather_than_an_empty_hot_set(self) -> None:
        """cap<=0 would otherwise score nothing at all — a misconfiguration must not
        silently disable the entire provisional layer."""
        hot = _hot({1: "signal", 2: "watchlist"})
        assert apply_hotset_cap(hot, cap=0) == (hot, 0)
        assert apply_hotset_cap(hot, cap=-5) == (hot, 0)

