"""Track-T tests: throttled Kite REST client + intraday backfill mechanics.

No live Kite calls — the client is exercised against stubbed kiteconnect
callables; the upsert seam runs on the real test Postgres (testing.md:
test the seams, never mock the DB).
"""

from __future__ import annotations

import asyncio
import sys
import time as _time
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import app.broker.kite_rest as kite_rest
import pytest
from app.broker.kite_rest import ThrottledKite
from app.models.market_data import Ohlcv5m
from kiteconnect.exceptions import NetworkException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from tests.helpers import make_stock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from backfill_intraday import (  # noqa: E402
    chunk_ranges,
    gap_verdict,
    in_session_window,
    rows_from_candles,
)

IST = ZoneInfo("Asia/Kolkata")


class TestChunkRanges:
    def test_span_splits_into_inclusive_60_day_windows(self) -> None:
        chunks = chunk_ranges(date(2024, 1, 1), date(2024, 4, 30))
        assert chunks[0] == (date(2024, 1, 1), date(2024, 2, 29))
        assert chunks[1][0] == date(2024, 3, 1)  # no overlap, no gap
        assert chunks[-1][1] == date(2024, 4, 30)
        assert all((hi - lo).days <= 59 for lo, hi in chunks)

    def test_short_span_is_one_window(self) -> None:
        assert chunk_ranges(date(2024, 1, 1), date(2024, 1, 5)) == [
            (date(2024, 1, 1), date(2024, 1, 5))
        ]

    def test_single_day_and_inverted(self) -> None:
        assert chunk_ranges(date(2024, 1, 1), date(2024, 1, 1)) == [
            (date(2024, 1, 1), date(2024, 1, 1))
        ]
        assert chunk_ranges(date(2024, 1, 2), date(2024, 1, 1)) == []


class TestSessionWindow:
    @pytest.mark.parametrize(
        ("hh", "mm", "ok"),
        [(9, 14, False), (9, 15, True), (12, 0, True), (15, 25, True),
         (15, 29, True), (15, 30, False), (9, 7, False)],
    )
    def test_bar_start_bounds(self, hh: int, mm: int, ok: bool) -> None:
        dt = datetime(2024, 7, 1, hh, mm, tzinfo=IST)
        assert in_session_window(dt) is ok


class TestRowsFromCandles:
    def test_ist_to_utc_conversion_and_filtering(self) -> None:
        candles = [
            {"date": datetime(2024, 7, 1, 9, 15, tzinfo=IST),
             "open": 100.5, "high": 101, "low": 100, "close": 100.75, "volume": 5000},
            {"date": datetime(2024, 7, 1, 9, 7, tzinfo=IST),  # pre-open — dropped
             "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        ]
        rows = rows_from_candles(42, candles)
        assert len(rows) == 1
        r = rows[0]
        # 09:15 IST == 03:45 UTC — the half-hour offset canon
        assert r["time"] == datetime(2024, 7, 1, 3, 45, tzinfo=UTC)
        assert r["stock_id"] == 42
        assert r["open"] == "100.5" and r["close"] == "100.75"  # str → Decimal-safe bind
        assert r["volume"] == 5000
        assert r["is_complete"] is True

    def test_naive_datetime_treated_as_ist(self) -> None:
        rows = rows_from_candles(
            1,
            [{"date": datetime(2024, 7, 1, 10, 0), "open": 1, "high": 1, "low": 1,
              "close": 1, "volume": 1}],
        )
        assert rows[0]["time"] == datetime(2024, 7, 1, 4, 30, tzinfo=UTC)


class TestGapVerdict:
    def test_threshold_boundary(self) -> None:
        assert gap_verdict(95, 100, 0.05) == (0.05, True)
        assert gap_verdict(94, 100, 0.05) == (0.06, False)

    def test_no_expected_sessions_is_fully_gapped(self) -> None:
        assert gap_verdict(0, 0, 0.05) == (1.0, False)

    def test_complete_coverage(self) -> None:
        assert gap_verdict(100, 100, 0.05) == (0.0, True)


class TestUpsertNeverReplaces:
    async def test_conflict_keeps_original_row(self, db) -> None:  # noqa: ANN001
        """Idempotency + never-replace: a second insert at the same
        (time, stock_id) with DIFFERENT prices must change nothing."""
        stock = await make_stock(db, symbol="BFTEST")
        t = datetime(2024, 7, 1, 3, 45, tzinfo=UTC)
        row = {"time": t, "stock_id": stock.id, "open": "100", "high": "101",
               "low": "99", "close": "100.5", "volume": 1000, "is_complete": True}
        conflicting = {**row, "close": "999", "volume": 9}

        for payload in ([row], [row, ], [conflicting]):
            stmt = pg_insert(Ohlcv5m).values(payload)
            await db.execute(stmt.on_conflict_do_nothing(index_elements=["time", "stock_id"]))
        await db.commit()

        stored = (
            await db.execute(select(Ohlcv5m).where(Ohlcv5m.stock_id == stock.id))
        ).scalars().all()
        assert len(stored) == 1
        assert str(stored[0].close) == "100.5000"  # original kept, Numeric(12,4)
        assert stored[0].volume == 1000


class TestThrottledKite:
    def test_calls_are_spaced_by_min_interval(self) -> None:
        tk = ThrottledKite("tok", min_interval_s=0.05)
        stamps: list[float] = []

        def fake(**_kw) -> list:  # noqa: ANN003
            stamps.append(_time.monotonic())
            return []

        tk._kc.historical_data = fake  # type: ignore[method-assign]

        async def run() -> None:
            for _ in range(3):
                await tk.historical_data(1, datetime(2024, 1, 1), datetime(2024, 1, 2), "5minute")

        asyncio.run(run())
        assert len(stamps) == 3
        assert all(b - a >= 0.045 for a, b in zip(stamps, stamps[1:], strict=False))

    def test_retries_transient_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kite_rest, "_BACKOFF_S", (0.01, 0.01, 0.01))
        tk = ThrottledKite("tok", min_interval_s=0.0)
        calls = {"n": 0}

        def flaky(**_kw) -> list[dict]:  # noqa: ANN003
            calls["n"] += 1
            if calls["n"] < 3:
                raise NetworkException("Too many requests")
            return [{"date": datetime(2024, 1, 1, 10, 0, tzinfo=IST)}]

        tk._kc.historical_data = flaky  # type: ignore[method-assign]
        out = asyncio.run(
            tk.historical_data(1, datetime(2024, 1, 1), datetime(2024, 1, 2), "5minute")
        )
        assert calls["n"] == 3 and len(out) == 1

    def test_exhausted_retries_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kite_rest, "_BACKOFF_S", (0.01, 0.01, 0.01))
        tk = ThrottledKite("tok", min_interval_s=0.0)

        def dead(**_kw) -> list:  # noqa: ANN003
            raise NetworkException("boom")

        tk._kc.historical_data = dead  # type: ignore[method-assign]
        with pytest.raises(NetworkException, match="boom"):
            asyncio.run(
                tk.historical_data(1, datetime(2024, 1, 1), datetime(2024, 1, 2), "5minute")
            )


class TestResumePointQuery:
    async def test_backfill_resumes_from_last_stored_bar(self, db) -> None:  # noqa: ANN001
        """The resume helper must return the LAST stored session (IST) so
        reruns refetch only from there — seam between DB state and the
        chunking that feeds Kite requests."""
        from backfill_intraday import _last_stored

        stock = await make_stock(db, symbol="RESUMECO")
        assert await _last_stored(db, Ohlcv5m, stock.id) is None
        for day, hh_utc in ((1, 3), (2, 3), (2, 9)):
            await db.execute(
                pg_insert(Ohlcv5m).values(
                    time=datetime(2024, 7, day, hh_utc, 45, tzinfo=UTC),
                    stock_id=stock.id, open="1", high="1", low="1", close="1",
                    volume=1, is_complete=True,
                ).on_conflict_do_nothing(index_elements=["time", "stock_id"])
            )
        await db.commit()
        # 2024-07-02 09:45 UTC == 15:15 IST same day → resume day is the 2nd
        assert await _last_stored(db, Ohlcv5m, stock.id) == date(2024, 7, 2)
