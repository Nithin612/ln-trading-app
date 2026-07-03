"""Tick-to-candle aggregation.

CandleAggregator receives raw Kite ticks and maintains in-memory OHLCV state
for multiple timeframes (1m, 5m, 15m, 1h).  When a candle period closes it:
  1. Marks the candle complete
  2. Yields a CandleEvent to the caller (for DB persistence + Redis pub/sub)

Key invariants:
- A candle at time T is open until the next tick lands in period T+N.
- Volume is cumulative for the period.
- `is_complete=False` ticks update an existing row; `is_complete=True` closes it.
- We never emit a signal on the same candle that triggers it (look-ahead safe).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

TIMEFRAMES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

# Map timeframe label → DB table name
TIMEFRAME_TABLE: dict[str, str] = {
    "1m": "ohlcv_1m",
    "5m": "ohlcv_5m",
    "15m": "ohlcv_15m",
    "1h": "ohlcv_1h",
}


@dataclass
class Candle:
    stock_id: int
    timeframe: str
    period_start: datetime        # UTC, floor of period
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    is_complete: bool = False

    def update(self, price: Decimal, volume: int) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += volume


@dataclass
class CandleEvent:
    """Emitted every time a candle is created or completed."""
    candle: Candle
    is_new: bool       # True = first tick of a new candle
    is_closed: bool    # True = previous candle just closed


@dataclass
class _TfState:
    """In-memory state for one (stock_id, timeframe) pair."""
    current: Candle | None = None
    minutes: int = 1


class CandleAggregator:
    """One instance per stock being subscribed to."""

    def __init__(self, stock_id: int) -> None:
        self.stock_id = stock_id
        self._state: dict[str, _TfState] = {
            tf: _TfState(minutes=mins)
            for tf, mins in TIMEFRAMES.items()
        }

    def on_tick(self, tick: dict[str, Any]) -> list[CandleEvent]:
        """Process one Kite tick dict and return zero or more CandleEvents."""
        # Kite tick timestamp may be None on some tick modes; fall back to now()
        ts_raw = tick.get("timestamp") or tick.get("last_trade_time")
        if ts_raw is None:
            tick_time = datetime.now(UTC)
        elif isinstance(ts_raw, datetime):
            tick_time = ts_raw.astimezone(UTC) if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
        else:
            # string "2024-01-15 09:16:00"
            tick_time = datetime.strptime(str(ts_raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

        ltp = tick.get("last_price") or tick.get("last_traded_price", 0)
        if not ltp:
            return []
        price = Decimal(str(ltp))
        traded_volume = int(tick.get("last_traded_quantity") or tick.get("last_quantity", 0))
        vol_delta = traded_volume if traded_volume else 0

        events: list[CandleEvent] = []
        for tf, state in self._state.items():
            period_start = _floor_to_period(tick_time, state.minutes)
            if state.current is None:
                # First tick ever
                state.current = Candle(
                    stock_id=self.stock_id,
                    timeframe=tf,
                    period_start=period_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=vol_delta,
                )
                events.append(CandleEvent(candle=state.current, is_new=True, is_closed=False))
            elif period_start > state.current.period_start:
                # Candle closed — emit closed event for OLD candle, then new candle
                closed = state.current
                closed.is_complete = True
                events.append(CandleEvent(candle=closed, is_new=False, is_closed=True))
                state.current = Candle(
                    stock_id=self.stock_id,
                    timeframe=tf,
                    period_start=period_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=vol_delta,
                )
                events.append(CandleEvent(candle=state.current, is_new=True, is_closed=False))
            else:
                # Same period — update in place
                state.current.update(price, vol_delta)
                events.append(CandleEvent(candle=state.current, is_new=False, is_closed=False))

        return events

    def get_current(self, timeframe: str) -> Candle | None:
        return self._state[timeframe].current if timeframe in self._state else None


def _floor_to_period(dt: datetime, minutes: int) -> datetime:
    """Floor a datetime to the nearest N-minute boundary."""
    total_minutes = dt.hour * 60 + dt.minute
    floored_minutes = (total_minutes // minutes) * minutes
    return dt.replace(
        hour=floored_minutes // 60,
        minute=floored_minutes % 60,
        second=0,
        microsecond=0,
    )


class AggregatorRegistry:
    """Holds one CandleAggregator per stock_id; thread-safe for read, not write."""

    def __init__(self) -> None:
        self._aggs: dict[int, CandleAggregator] = {}

    def get_or_create(self, stock_id: int) -> CandleAggregator:
        if stock_id not in self._aggs:
            self._aggs[stock_id] = CandleAggregator(stock_id)
        return self._aggs[stock_id]

    def remove(self, stock_id: int) -> None:
        self._aggs.pop(stock_id, None)

    def all_stock_ids(self) -> list[int]:
        return list(self._aggs.keys())
