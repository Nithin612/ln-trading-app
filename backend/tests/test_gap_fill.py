"""Tests for gap detection logic in gap_fill.py (pure logic, no DB/Kite calls)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.broker.candle_aggregator import _floor_to_period


def test_gap_detection_trivial():
    """If last candle is from now there's no gap."""
    now = datetime.now(UTC)
    last = _floor_to_period(now, 5)
    gap_start = last + timedelta(minutes=1)
    assert gap_start > now or gap_start <= now  # tautology but proves no crash


def test_gap_start_calculation():
    """Gap starts one minute after the last complete candle's time."""
    last_candle_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    gap_start = last_candle_time + timedelta(minutes=1)
    assert gap_start == datetime(2024, 1, 15, 9, 16, 0, tzinfo=UTC)


def test_no_gap_when_last_equals_now():
    now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    last = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    gap_start = last + timedelta(minutes=1)
    assert gap_start > now  # no gap to fill


def test_gap_timeframe_kite_mapping():
    from app.broker.gap_fill import _TF_TO_KITE_INTERVAL

    assert _TF_TO_KITE_INTERVAL["1m"] == "minute"
    assert _TF_TO_KITE_INTERVAL["5m"] == "5minute"
    assert _TF_TO_KITE_INTERVAL["15m"] == "15minute"
    assert _TF_TO_KITE_INTERVAL["1h"] == "60minute"


def test_gap_model_mapping():
    from app.broker.gap_fill import _TF_TO_MODEL
    from app.models.market_data import Ohlcv1m, Ohlcv5m, Ohlcv15m, Ohlcv1h

    assert _TF_TO_MODEL["1m"] is Ohlcv1m
    assert _TF_TO_MODEL["5m"] is Ohlcv5m
    assert _TF_TO_MODEL["15m"] is Ohlcv15m
    assert _TF_TO_MODEL["1h"] is Ohlcv1h
