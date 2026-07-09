"""Tests for the tick-to-candle aggregation logic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.broker.candle_aggregator import (
    AggregatorRegistry,
    CandleAggregator,
    _floor_to_period,
)


def _tick(ltp: float, ts: datetime, volume: int = 100) -> dict:
    # Mirrors kiteconnect's actual field names: `exchange_timestamp` (never
    # "timestamp") and cumulative `volume_traded`.
    return {
        "instrument_token": 12345,
        "last_price": ltp,
        "exchange_timestamp": ts,
        "last_traded_quantity": volume,
        "volume_traded": volume * 10,
    }


# ── _floor_to_period ─────────────────────────────────────────────────────────

def test_floor_to_period_1m():
    dt = datetime(2024, 1, 15, 9, 17, 43, tzinfo=UTC)
    assert _floor_to_period(dt, 1) == datetime(2024, 1, 15, 9, 17, 0, tzinfo=UTC)


def test_floor_to_period_5m():
    dt = datetime(2024, 1, 15, 9, 23, 10, tzinfo=UTC)
    assert _floor_to_period(dt, 5) == datetime(2024, 1, 15, 9, 20, 0, tzinfo=UTC)


def test_floor_to_period_15m():
    dt = datetime(2024, 1, 15, 10, 14, 59, tzinfo=UTC)
    assert _floor_to_period(dt, 15) == datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)


def test_floor_to_period_1h_session_anchored():
    """Slice-3.2 regression: 1h buckets anchor at 09:15 IST (03:45 UTC),
    not UTC hours — the old floor put a 10:20 IST tick into a 09:30 IST
    candle; the canon bucket is 10:15 IST."""
    dt = datetime(2024, 1, 15, 4, 50, 0, tzinfo=UTC)  # 10:20 IST
    assert _floor_to_period(dt, 60) == datetime(2024, 1, 15, 4, 45, 0, tzinfo=UTC)
    # exact anchor boundary stays put
    dt = datetime(2024, 1, 15, 13, 45, 0, tzinfo=UTC)
    assert _floor_to_period(dt, 60) == datetime(2024, 1, 15, 13, 45, 0, tzinfo=UTC)
    # sub-hour timeframes are arithmetically unchanged by the anchor
    dt = datetime(2024, 1, 15, 10, 14, 59, tzinfo=UTC)
    assert _floor_to_period(dt, 15) == datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    assert _floor_to_period(dt, 5) == datetime(2024, 1, 15, 10, 10, 0, tzinfo=UTC)


def test_floor_to_period_boundary_exact():
    dt = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    assert _floor_to_period(dt, 5) == datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)


# ── CandleAggregator basic ────────────────────────────────────────────────────

def test_first_tick_creates_candle():
    agg = CandleAggregator(stock_id=1)
    t = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    events = agg.on_tick(_tick(100.0, t))
    assert len(events) > 0
    # Every timeframe emits a new-candle event
    new_events = [e for e in events if e.is_new]
    assert len(new_events) == 4  # 1m, 5m, 15m, 1h


def test_same_period_updates_ohlc():
    agg = CandleAggregator(stock_id=1)
    t0 = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    t1 = datetime(2024, 1, 15, 9, 15, 30, tzinfo=UTC)
    t2 = datetime(2024, 1, 15, 9, 15, 50, tzinfo=UTC)

    agg.on_tick(_tick(100.0, t0))
    agg.on_tick(_tick(105.0, t1))
    agg.on_tick(_tick(98.0, t2))

    candle_1m = agg.get_current("1m")
    assert candle_1m is not None
    assert candle_1m.open == Decimal("100.0")
    assert candle_1m.high == Decimal("105.0")
    assert candle_1m.low == Decimal("98.0")
    assert candle_1m.close == Decimal("98.0")
    assert candle_1m.is_complete is False


def test_new_period_emits_closed_event():
    agg = CandleAggregator(stock_id=1)
    t0 = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    t1 = datetime(2024, 1, 15, 9, 16, 0, tzinfo=UTC)  # next 1m period

    agg.on_tick(_tick(100.0, t0))
    events = agg.on_tick(_tick(102.0, t1))

    closed = [e for e in events if e.is_closed]
    assert any(e.candle.timeframe == "1m" for e in closed), "1m candle should close"
    closed_1m = next(e for e in closed if e.candle.timeframe == "1m")
    assert closed_1m.candle.is_complete is True
    assert closed_1m.candle.close == Decimal("100.0")


def test_candle_high_low_maintained():
    agg = CandleAggregator(stock_id=1)
    base = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    prices = [100.0, 110.0, 90.0, 105.0, 95.0]
    for i, p in enumerate(prices):
        agg.on_tick(_tick(p, base + timedelta(seconds=i * 5)))

    c = agg.get_current("1m")
    assert c is not None
    assert float(c.high) == 110.0
    assert float(c.low) == 90.0
    assert float(c.close) == 95.0


def test_5m_candle_aggregates_multiple_1m():
    agg = CandleAggregator(stock_id=2)
    base = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)

    # 4 ticks in the 9:15-9:20 5m bucket
    for i in range(4):
        agg.on_tick(_tick(100.0 + i, base + timedelta(minutes=i)))

    c5 = agg.get_current("5m")
    assert c5 is not None
    assert c5.period_start == datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    assert float(c5.open) == 100.0
    assert float(c5.close) == 103.0

    # Tick in next 5m period → previous 5m closes
    events = agg.on_tick(_tick(200.0, base + timedelta(minutes=5)))
    closed_5m = [e for e in events if e.is_closed and e.candle.timeframe == "5m"]
    assert len(closed_5m) == 1
    assert closed_5m[0].candle.is_complete is True


def test_no_events_for_zero_price():
    agg = CandleAggregator(stock_id=3)
    t = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    events = agg.on_tick(
        {"instrument_token": 123, "last_price": 0, "exchange_timestamp": t}
    )
    assert events == []


# ── Timestamp regression (kiteconnect sends NAIVE host-local datetimes) ──────

def test_naive_host_local_timestamp_converted_not_relabelled():
    """kiteconnect's exchange_timestamp is naive host-local; the aggregator
    must CONVERT it to UTC (astimezone), not stamp it as UTC (replace) —
    on an IST host the old behavior mislabelled every candle by +5:30."""
    agg = CandleAggregator(stock_id=7)
    naive_local = datetime(2026, 7, 3, 9, 30, 0)  # naive, host zone
    expected_utc = naive_local.astimezone(UTC)    # correct conversion

    agg.on_tick(_tick(100.0, naive_local))
    c = agg.get_current("1m")
    assert c is not None
    assert c.period_start == expected_utc.replace(second=0, microsecond=0)


def test_legacy_timestamp_key_is_ignored():
    """kiteconnect never sets a "timestamp" key — a tick carrying only that
    key must fall back to now(), not silently use a stale value."""
    agg = CandleAggregator(stock_id=8)
    stale = datetime(2020, 1, 1, 9, 15, 0, tzinfo=UTC)
    agg.on_tick({"instrument_token": 1, "last_price": 100.0, "timestamp": stale})
    c = agg.get_current("1m")
    assert c is not None
    assert c.period_start.year >= 2026  # now(), not the stale 2020 stamp


# ── Volume regression (cumulative diff, not snapshot-quantity summing) ────────

def test_volume_diffs_cumulative_day_volume():
    agg = CandleAggregator(stock_id=9)
    base = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)

    def tick_with_dayvol(ltp: float, ts: datetime, day_vol: int, lastqty: int) -> dict:
        return {
            "instrument_token": 1,
            "last_price": ltp,
            "exchange_timestamp": ts,
            "last_traded_quantity": lastqty,
            "volume_traded": day_vol,
        }

    # First tick: no baseline → 0 (not the whole day's volume)
    agg.on_tick(tick_with_dayvol(100.0, base, day_vol=5000, lastqty=50))
    # Quote-only tick: same cumulative volume, lastqty repeated → adds 0
    agg.on_tick(tick_with_dayvol(100.5, base + timedelta(seconds=1), day_vol=5000, lastqty=50))
    # Real trades between snapshots: cumulative jumps 300 → adds 300
    agg.on_tick(tick_with_dayvol(101.0, base + timedelta(seconds=2), day_vol=5300, lastqty=50))

    c = agg.get_current("1m")
    assert c is not None
    assert c.volume == 300  # old summing logic would have said 150


def test_volume_falls_back_to_lastqty_without_cumulative():
    agg = CandleAggregator(stock_id=10)
    base = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    agg.on_tick(
        {
            "instrument_token": 1,
            "last_price": 100.0,
            "exchange_timestamp": base,
            "last_traded_quantity": 75,
        }
    )
    c = agg.get_current("1m")
    assert c is not None
    assert c.volume == 75


# ── AggregatorRegistry ────────────────────────────────────────────────────────

def test_registry_get_or_create():
    reg = AggregatorRegistry()
    a1 = reg.get_or_create(1)
    a2 = reg.get_or_create(1)
    assert a1 is a2  # same instance


def test_registry_remove():
    reg = AggregatorRegistry()
    reg.get_or_create(10)
    reg.remove(10)
    # Creating again returns a fresh (empty) aggregator
    agg = reg.get_or_create(10)
    assert agg.get_current("1m") is None


def test_registry_all_stock_ids():
    reg = AggregatorRegistry()
    reg.get_or_create(1)
    reg.get_or_create(2)
    reg.get_or_create(3)
    assert sorted(reg.all_stock_ids()) == [1, 2, 3]
