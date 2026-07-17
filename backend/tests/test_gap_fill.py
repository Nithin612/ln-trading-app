"""Gap-fill tests: pure mapping logic + the detect→fetch→upsert seam.

The seam tests run against the real test Postgres with a stubbed
ThrottledKite (testing.md: test the seams, never mock the DB). They pin
the 2026-07-17 routing fix: gap-fill fetches through the caller's SHARED
ThrottledKite — the old `fetch_historical` built a raw unthrottled
KiteConnect per call, which at full-universe scale (~6,165 requests) drew
intermittent `invalid token` (the 07-13 rebuild failure).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from app.broker.gap_fill import _TF_TO_KITE_INTERVAL, _TF_TO_MODEL, detect_and_fill_gaps
from app.broker.kite_rest import KiteException, ThrottledKite, TokenException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

IST = ZoneInfo("Asia/Kolkata")

# A fixed past session moment (2026-07-01 09:15 IST) — tests must not
# depend on wall-clock date, only on "gap_start < now".
LAST_5M = datetime(2026, 7, 1, 3, 45, tzinfo=UTC)


class _StubKite:
    """historical_data seam: canned candles per interval, or raise."""

    def __init__(self, candles: dict[str, list[dict[str, Any]] | Exception]):
        self._candles = candles
        self.calls: list[tuple[int, str, datetime, datetime]] = []

    async def historical_data(
        self,
        instrument_token: int,
        from_dt: datetime,
        to_dt: datetime,
        interval: str,
    ) -> list[dict[str, Any]]:
        self.calls.append((instrument_token, interval, from_dt, to_dt))
        out = self._candles.get(interval, [])
        if isinstance(out, Exception):
            raise out
        return out


async def _seed_complete(db: AsyncSession, table: str, stock_id: int, t: datetime) -> None:
    await db.execute(
        text(
            f"INSERT INTO {table} (time, stock_id, open, high, low, close,"  # noqa: S608
            " volume, is_complete) VALUES (:t, :sid, 1, 1, 1, 1, 1, true)"
        ),
        {"t": t, "sid": stock_id},
    )


class TestDetectAndFillGapsSeam:
    async def test_fills_through_the_shared_throttled_client(self, db: AsyncSession) -> None:
        """Regression (2026-07-17): the fetch must go through the passed
        ThrottledKite — the old code took a token string and built its own
        unthrottled client per call, so no shared instance could ever
        space the requests."""
        stock = await make_stock(db, symbol="GAPSEAM")
        await _seed_complete(db, "ohlcv_5m", stock.id, LAST_5M)
        kite = _StubKite(
            {
                "5minute": [
                    {
                        "date": (LAST_5M + timedelta(minutes=5)).astimezone(IST),
                        "open": 101.5,
                        "high": 102.0,
                        "low": 100.9,
                        "close": 101.95,
                        "volume": 1200,
                    }
                ]
            }
        )

        results = await detect_and_fill_gaps(
            db, cast(ThrottledKite, kite), 777, stock.id, timeframes=["5m"]
        )

        assert results == {"5m": 1}
        # exactly one fetch, through the stub, with the detected window —
        # sent as NAIVE IST wall time (bug-hunter HIGH, 2026-07-17:
        # kiteconnect strftimes wall time and Kite reads it as IST; the
        # old UTC-aware window was shifted 5.5 h into the past, so
        # mid-session outage candles were never requested)
        assert len(kite.calls) == 1
        instrument_token, interval, from_dt, to_dt = kite.calls[0]
        assert instrument_token == 777
        assert interval == "5minute"
        assert from_dt.tzinfo is None and to_dt.tzinfo is None
        assert from_dt == (LAST_5M + timedelta(minutes=1)).astimezone(IST).replace(tzinfo=None)
        # upserted VALUES, not just a count (Numeric(12,4) exactness)
        row = (
            await db.execute(
                text(
                    "SELECT open, high, low, close, volume, is_complete FROM ohlcv_5m"
                    " WHERE stock_id = :sid AND time = :t"
                ),
                {"sid": stock.id, "t": LAST_5M + timedelta(minutes=5)},
            )
        ).one()
        assert row[0] == Decimal("101.5000")
        assert row[1] == Decimal("102.0000")
        assert row[2] == Decimal("100.9000")
        assert row[3] == Decimal("101.9500")
        assert row[4] == 1200
        assert row[5] is True

    async def test_kite_failure_isolated_per_timeframe(self, db: AsyncSession) -> None:
        """A failing fetch zeroes THAT timeframe and moves on — one bad
        instrument/interval must not abort the rest (error path per
        testing.md). KiteException here models the stale-instrument
        `InputException: invalid token` class from the 07-13 rebuild —
        isolated, NOT fatal (unlike TokenException below)."""
        stock = await make_stock(db, symbol="GAPFAIL")
        await _seed_complete(db, "ohlcv_5m", stock.id, LAST_5M)
        await _seed_complete(db, "ohlcv_15m", stock.id, LAST_5M)
        kite = _StubKite(
            {
                "5minute": KiteException("Invalid token"),
                "15minute": [
                    {
                        "date": (LAST_5M + timedelta(minutes=15)).astimezone(IST),
                        "open": 50,
                        "high": 51,
                        "low": 49,
                        "close": 50.5,
                        "volume": 900,
                    }
                ],
            }
        )

        results = await detect_and_fill_gaps(
            db, cast(ThrottledKite, kite), 888, stock.id, timeframes=["5m", "15m"]
        )

        assert results == {"5m": 0, "15m": 1}
        n = (
            await db.execute(
                text("SELECT count(*) FROM ohlcv_15m WHERE stock_id = :sid"),
                {"sid": stock.id},
            )
        ).scalar()
        assert n == 2  # seed + filled

    async def test_no_existing_data_skips_without_fetching(self, db: AsyncSession) -> None:
        """Empty table → no resume point → no REST call at all."""
        stock = await make_stock(db, symbol="GAPEMPTY")
        kite = _StubKite({})

        results = await detect_and_fill_gaps(
            db, cast(ThrottledKite, kite), 999, stock.id, timeframes=["5m"]
        )

        assert results == {"5m": 0}
        assert kite.calls == []

    async def test_dead_session_token_aborts_immediately(self, db: AsyncSession) -> None:
        """TokenException = the SESSION token is dead (daily ~6 AM IST
        expiry) — every further paced call this run is doomed. It must
        escape the per-timeframe catch-all so the caller can abort,
        without even attempting the remaining timeframes (bug-hunter
        MEDIUM, 2026-07-17: it used to be swallowed and the full-universe
        loop ground ~6,165 futile throttled calls ≈ 35 min)."""
        stock = await make_stock(db, symbol="GAPDEAD")
        await _seed_complete(db, "ohlcv_5m", stock.id, LAST_5M)
        await _seed_complete(db, "ohlcv_15m", stock.id, LAST_5M)
        kite = _StubKite({"5minute": TokenException("Incorrect `api_key` or `access_token`.")})

        with pytest.raises(TokenException):
            await detect_and_fill_gaps(
                db, cast(ThrottledKite, kite), 777, stock.id, timeframes=["5m", "15m"]
            )
        assert len(kite.calls) == 1  # 15m never attempted


def test_gap_start_calculation() -> None:
    """Gap starts one minute after the last complete candle's time."""
    last_candle_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC)
    gap_start = last_candle_time + timedelta(minutes=1)
    assert gap_start == datetime(2024, 1, 15, 9, 16, 0, tzinfo=UTC)


def test_no_gap_when_last_equals_now() -> None:
    now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    last = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    gap_start = last + timedelta(minutes=1)
    assert gap_start > now  # no gap to fill


def test_gap_timeframe_kite_mapping() -> None:
    assert _TF_TO_KITE_INTERVAL["1m"] == "minute"
    assert _TF_TO_KITE_INTERVAL["5m"] == "5minute"
    assert _TF_TO_KITE_INTERVAL["15m"] == "15minute"
    assert _TF_TO_KITE_INTERVAL["1h"] == "60minute"


def test_gap_model_mapping() -> None:
    from app.models.market_data import Ohlcv1h, Ohlcv1m, Ohlcv5m, Ohlcv15m

    assert _TF_TO_MODEL["1m"] is Ohlcv1m
    assert _TF_TO_MODEL["5m"] is Ohlcv5m
    assert _TF_TO_MODEL["15m"] is Ohlcv15m
    assert _TF_TO_MODEL["1h"] is Ohlcv1h
