"""Session-aligned ohlcv_1h rollup (Phase 3 slice 3.2).

Real-DB tests: seed 5m bars, run the SAME SQL the migration executes,
assert the slice-3.1 bucket canon lands in the table — 09:15-anchored
hourly buckets with the 15:15–15:30 stub, forming hours excluded via an
injected as_of cutoff (no wall-clock dependence).
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.ohlcv_rollup import rebuild_ohlcv_1h
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_intraday_candles, make_stock

IST = ZoneInfo("Asia/Kolkata")
DAY1, DAY2 = date(2026, 7, 6), date(2026, 7, 7)


def _ist(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=IST)


def _session(base: float) -> list[tuple[float, float, float, float]]:
    """75 5m bars; bar i carries (base+i, base+i+0.5, base+i-0.5, base+i+0.25)
    so every 1h aggregate is hand-computable from its bar range."""
    return [(base + i, base + i + 0.5, base + i - 0.5, base + i + 0.25) for i in range(75)]


async def _rows(db: AsyncSession, stock_id: int) -> list:
    return (
        await db.execute(
            text(
                "SELECT time, open, high, low, close, volume, is_complete"
                " FROM ohlcv_1h WHERE stock_id = :sid ORDER BY time"
            ),
            {"sid": stock_id},
        )
    ).fetchall()


class TestRebuildOhlcv1h:
    async def test_canonical_buckets_with_stub_and_exact_ohlcv(
        self, db: AsyncSession
    ) -> None:
        stock = await make_stock(db, symbol="ROLL1")
        await make_intraday_candles(db, stock.id, "5m", [_session(100.0)], end_day=DAY1)

        inserted = await rebuild_ohlcv_1h(db, as_of=_ist(DAY1, 16, 0).astimezone(UTC))
        rows = await _rows(db, stock.id)
        assert inserted == len(rows) == 7

        starts = [r.time.astimezone(IST).strftime("%H:%M") for r in rows]
        assert starts == ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]

        # First hour = bars 0..11: open bar0, high bar11+0.5, low bar0-0.5,
        # close bar11+0.25, volume 12×50_000.
        first = rows[0]
        assert (first.open, first.high, first.low, first.close) == (
            Decimal("100"), Decimal("111.5"), Decimal("99.5"), Decimal("111.25"),
        )
        assert first.volume == 12 * 50_000
        # 15:15 stub = bars 72..74 only.
        stub = rows[6]
        assert (stub.open, stub.high, stub.low, stub.close) == (
            Decimal("172"), Decimal("174.5"), Decimal("171.5"), Decimal("174.25"),
        )
        assert stub.volume == 3 * 50_000
        assert all(r.is_complete for r in rows)

    async def test_forming_hour_excluded_by_as_of_cutoff(
        self, db: AsyncSession
    ) -> None:
        """Mid-session rollup: only fully-ended buckets mint — the forming
        hour must never land as is_complete (no-repaint discipline)."""
        stock = await make_stock(db, symbol="ROLL2")
        await make_intraday_candles(
            db, stock.id, "5m", [_session(100.0), _session(200.0)], end_day=DAY2
        )

        # as_of = DAY2 11:00 IST: day1 full (7); day2 only 09:15 (ends 10:15).
        await rebuild_ohlcv_1h(db, as_of=_ist(DAY2, 11, 0).astimezone(UTC))
        rows = await _rows(db, stock.id)
        assert len(rows) == 8
        assert rows[-1].time.astimezone(IST).strftime("%d %H:%M") == "07 09:15"

        # Later rerun (never-replace): tops up the rest of day2 only.
        added = await rebuild_ohlcv_1h(db, as_of=_ist(DAY2, 16, 0).astimezone(UTC))
        assert added == 6
        assert len(await _rows(db, stock.id)) == 14

    async def test_rerun_is_idempotent_and_never_replaces(
        self, db: AsyncSession
    ) -> None:
        stock = await make_stock(db, symbol="ROLL3")
        await make_intraday_candles(db, stock.id, "5m", [_session(100.0)], end_day=DAY1)
        cutoff = _ist(DAY1, 16, 0).astimezone(UTC)
        assert await rebuild_ohlcv_1h(db, as_of=cutoff) == 7
        assert await rebuild_ohlcv_1h(db, as_of=cutoff) == 0  # ON CONFLICT DO NOTHING

    async def test_delete_first_replaces_utc_floored_garbage(
        self, db: AsyncSession
    ) -> None:
        """The migration path: a v1 UTC-hour-floored row (10:30 IST anchor)
        is deleted, canon rows land."""
        stock = await make_stock(db, symbol="ROLL4")
        await db.execute(
            text(
                "INSERT INTO ohlcv_1h (time, stock_id, open, high, low, close,"
                " volume, is_complete) VALUES (:t, :sid, 1, 1, 1, 1, 1, true)"
            ),
            {"t": _ist(DAY1, 10, 30).astimezone(UTC), "sid": stock.id},
        )
        await db.commit()
        await make_intraday_candles(db, stock.id, "5m", [_session(100.0)], end_day=DAY1)

        await rebuild_ohlcv_1h(
            db, as_of=_ist(DAY1, 16, 0).astimezone(UTC), delete_first=True
        )
        starts = [r.time.astimezone(IST).strftime("%H:%M") for r in await _rows(db, stock.id)]
        assert "10:30" not in starts
        assert starts[0] == "09:15" and len(starts) == 7

    async def test_incomplete_and_out_of_session_bars_excluded(
        self, db: AsyncSession
    ) -> None:
        """Forming 5m bars and pre-open/post-close artifacts never
        aggregate (matches the backfill session guard)."""
        from app.models.market_data import Ohlcv5m

        stock = await make_stock(db, symbol="ROLL5")
        await make_intraday_candles(db, stock.id, "5m", [_session(100.0)], end_day=DAY1)
        artifacts = (
            (_ist(DAY1, 9, 0), True),  # pre-open artifact
            (_ist(DAY1, 15, 35), True),  # post-close artifact
            (_ist(DAY1 + timedelta(days=1), 15, 25), False),  # forming next-day bar
        )
        for t, complete in artifacts:
            db.add(
                Ohlcv5m(
                    time=t.astimezone(UTC),
                    stock_id=stock.id,
                    open=Decimal("999"), high=Decimal("999"),
                    low=Decimal("999"), close=Decimal("999"),
                    volume=1, is_complete=complete,
                )
            )
        await db.commit()

        await rebuild_ohlcv_1h(db, as_of=_ist(DAY1 + timedelta(days=2), 16, 0).astimezone(UTC))
        rows = await _rows(db, stock.id)
        assert len(rows) == 7  # nothing from the three artifact bars
        assert all(r.high != Decimal("999") for r in rows)
