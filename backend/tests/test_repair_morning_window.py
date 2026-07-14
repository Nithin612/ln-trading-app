"""Tests for scripts/repair_morning_window.py (soak #3 morning repair).

No live Kite calls — the fetch seam is a stubbed client; upserts and the
15m/1h recompute run on the real test Postgres (testing.md: test the
seams, never mock the DB). The core semantic under test is DO UPDATE:
unlike backfill_intraday's never-replace, the repair MUST overwrite
wrong live-minted rows with official data.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from app.broker.kite_rest import ThrottledKite, TokenException
from app.models.market_data import Ohlcv1h, Ohlcv5m, Ohlcv15m
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from tests.helpers import make_stock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from repair_morning_window import RECOMPUTE_SQL, _refetch_5m, _rows  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2024, 7, 1)
LO = datetime(2024, 7, 1, 9, 15, tzinfo=IST)
HI = datetime(2024, 7, 1, 9, 30, tzinfo=IST)
T0_UTC = datetime(2024, 7, 1, 3, 45, tzinfo=UTC)  # == 09:15 IST


def _candle(hh: int, mm: int, o: float, h: float, lo_: float, c: float, v: int) -> dict[str, Any]:
    return {
        "date": datetime(2024, 7, 1, hh, mm, tzinfo=IST),
        "open": o,
        "high": h,
        "low": lo_,
        "close": c,
        "volume": v,
    }


class _StubKite:
    """historical_data seam: canned candles per instrument_token, or raise."""

    def __init__(
        self,
        by_token: dict[int, list[dict[str, Any]]] | None = None,
        raise_for: set[int] | None = None,
    ) -> None:
        self.by_token = by_token or {}
        self.raise_for = raise_for or set()
        self.calls = 0

    async def historical_data(
        self, instrument_token: int, _frm: datetime, _to: datetime, _interval: str
    ) -> list[dict[str, Any]]:
        self.calls += 1
        if instrument_token in self.raise_for:
            raise TokenException("invalid token")
        return self.by_token.get(instrument_token, [])


class TestRows:
    def test_window_is_half_open_and_utc_converted(self) -> None:
        candles = [
            _candle(9, 10, 1, 1, 1, 1, 1),  # before lo — dropped
            _candle(9, 15, 100.5, 101, 100, 100.75, 5000),
            _candle(9, 25, 102, 103, 101, 102.5, 700),
            _candle(9, 30, 1, 1, 1, 1, 1),  # at hi (half-open) — dropped
        ]
        rows = _rows(42, candles, LO, HI)
        assert [r["time"] for r in rows] == [T0_UTC, T0_UTC + timedelta(minutes=10)]
        assert rows[0]["open"] == "100.5" and rows[0]["close"] == "100.75"  # str binds
        assert rows[0]["volume"] == 5000 and rows[0]["is_complete"] is True

    def test_naive_candle_datetime_treated_as_ist(self) -> None:
        naive = {
            "date": datetime(2024, 7, 1, 9, 15),
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 1,
        }
        assert _rows(1, [naive], LO, HI)[0]["time"] == T0_UTC


class TestRefetchReplacesWrongRows:
    async def test_do_update_overwrites_partial_live_row(self, db) -> None:  # noqa: ANN001
        """THE repair semantic: a live-minted row with a snapshot-tick open
        must be REPLACED by the official candle (backfill_intraday's
        DO-NOTHING would keep the wrong row — that is why this script
        exists)."""
        stock = await make_stock(db, symbol="REPAIRCO")
        wrong = {
            "time": T0_UTC,
            "stock_id": stock.id,
            "open": "203.2",  # 09:24 snapshot price
            "high": "203.2",
            "low": "203.2",
            "close": "203.2",
            "volume": 18,
            "is_complete": True,
        }
        await db.execute(
            pg_insert(Ohlcv5m)
            .values([wrong])
            .on_conflict_do_nothing(index_elements=["time", "stock_id"])
        )
        # a healthy live row AFTER the window — must remain untouched
        outside = {**wrong, "time": datetime(2024, 7, 1, 4, 30, tzinfo=UTC), "open": "777"}
        await db.execute(
            pg_insert(Ohlcv5m)
            .values([outside])
            .on_conflict_do_nothing(index_elements=["time", "stock_id"])
        )
        await db.commit()

        kite = _StubKite(by_token={111: [_candle(9, 15, 202, 203.1, 198.23, 201.94, 6956)]})
        result = await _refetch_5m(
            db, cast(ThrottledKite, kite), [(stock.id, 111, "REPAIRCO")], LO, HI, dry_run=False
        )
        assert result == (1, 0)

        stored = {
            r.time: r
            for r in (
                (await db.execute(select(Ohlcv5m).where(Ohlcv5m.stock_id == stock.id)))
                .scalars()
                .all()
            )
        }
        official = stored[T0_UTC]
        assert str(official.open) == "202.0000"  # replaced, Numeric(12,4)
        assert str(official.low) == "198.2300"
        assert official.volume == 6956
        untouched = stored[datetime(2024, 7, 1, 4, 30, tzinfo=UTC)]
        assert str(untouched.open) == "777.0000"  # outside the window — preserved

    async def test_intermittent_failure_is_tolerated_and_counted(self, db) -> None:  # noqa: ANN001
        """07-13/07-14 pattern: isolated 'invalid token' failures must not
        abort the run — count them and keep going."""
        ok = await make_stock(db, symbol="OKCO")
        kite = _StubKite(
            by_token={222: [_candle(9, 15, 10, 11, 9, 10.5, 100)]},
            raise_for={111},
        )
        result = await _refetch_5m(
            db,
            cast(ThrottledKite, kite),
            [(999999, 111, "FAILCO"), (ok.id, 222, "OKCO")],
            LO,
            HI,
            dry_run=False,
        )
        assert result == (1, 1)

    async def test_dead_token_tripwire_aborts(self, db) -> None:  # noqa: ANN001
        """If the FIRST 20 calls all fail the token is dead — abort (None),
        don't grind through 2,000 doomed requests."""
        kite = _StubKite(raise_for=set(range(1, 21)))
        universe = [(10_000 + t, t, f"S{t}") for t in range(1, 26)]
        result = await _refetch_5m(db, cast(ThrottledKite, kite), universe, LO, HI, dry_run=False)
        assert result is None
        assert kite.calls == 20  # stopped at the tripwire, not the full universe


class TestRecompute:
    async def _seed_5m(
        self, db, stock_id: int, bars: list[tuple[int, int, str, str, str, str, int, bool]]
    ) -> None:  # noqa: ANN001, E501
        for hh, mm, o, h, lo_, c, v, complete in bars:
            await db.execute(
                pg_insert(Ohlcv5m)
                .values(
                    time=datetime(2024, 7, 1, hh, mm, tzinfo=UTC),
                    stock_id=stock_id,
                    open=o,
                    high=h,
                    low=lo_,
                    close=c,
                    volume=v,
                    is_complete=complete,
                )
                .on_conflict_do_nothing(index_elements=["time", "stock_id"])
            )
        await db.commit()

    async def test_15m_and_1h_buckets_are_exact_5m_aggregates(self, db) -> None:  # noqa: ANN001
        stock = await make_stock(db, symbol="AGGCO")
        await self._seed_5m(
            db,
            stock.id,
            [
                # the repaired window (03:45–04:00 UTC == 09:15–09:30 IST)
                (3, 45, "100", "105", "99", "101", 10, True),
                (3, 50, "101", "110", "100", "108", 20, True),
                (3, 55, "108", "109", "95", "96", 5, True),
                # a live bar in the next 15m bucket but inside the hour
                (4, 0, "96", "97", "90", "92", 7, True),
                # a FORMING bar inside the window — must be ignored
                (3, 55, "1", "99999", "0.1", "1", 999, False),
            ],
        )
        # pre-existing WRONG 15m row (live-minted from snapshot ticks)
        await db.execute(
            pg_insert(Ohlcv15m)
            .values(
                time=T0_UTC,
                stock_id=stock.id,
                open="999",
                high="999",
                low="999",
                close="999",
                volume=1,
                is_complete=True,
            )
            .on_conflict_do_nothing(index_elements=["time", "stock_id"])
        )
        await db.commit()

        for table, minutes in (("ohlcv_15m", 15), ("ohlcv_1h", 60)):
            await db.execute(
                text(RECOMPUTE_SQL.format(table=table)),
                {"t0": T0_UTC, "t1": T0_UTC + timedelta(minutes=minutes)},
            )
        await db.commit()

        m15 = (
            await db.execute(
                select(Ohlcv15m).where(Ohlcv15m.stock_id == stock.id, Ohlcv15m.time == T0_UTC)
            )
        ).scalar_one()
        assert (str(m15.open), str(m15.high), str(m15.low), str(m15.close), m15.volume) == (
            "100.0000",
            "110.0000",
            "95.0000",
            "96.0000",
            35,
        )
        assert m15.is_complete is True

        h1 = (
            await db.execute(
                select(Ohlcv1h).where(Ohlcv1h.stock_id == stock.id, Ohlcv1h.time == T0_UTC)
            )
        ).scalar_one()
        # hour bucket also swallows the 04:00 bar: close/low move, volume sums
        assert (str(h1.open), str(h1.high), str(h1.low), str(h1.close), h1.volume) == (
            "100.0000",
            "110.0000",
            "90.0000",
            "92.0000",
            42,
        )

        # the recompute is scoped: no 15m row minted outside the t0 bucket
        next_bucket = datetime(2024, 7, 1, 4, 0, tzinfo=UTC)
        other = (
            await db.execute(
                select(Ohlcv15m).where(Ohlcv15m.stock_id == stock.id, Ohlcv15m.time == next_bucket)
            )
        ).scalar_one_or_none()
        assert other is None
