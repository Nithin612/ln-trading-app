"""Corporate-action quarantine (Phase 2 slice 6).

A split in unadjusted bhavcopy data looks like a huge overnight gap; the
detector must flag it, and flagged stocks must vanish from suggestion
universes — scored-across-a-split windows are data poison.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.market_data import OhlcvDaily
from app.services.ca_detector import scan_for_discontinuities
from app.services.universe_service import resolve_universe
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

SESSION = date(2026, 7, 3)


async def _candle(db: AsyncSession, stock_id: int, d: date, open_: str, close: str) -> None:
    db.add(
        OhlcvDaily(
            time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
            stock_id=stock_id,
            open=Decimal(open_),
            high=Decimal(close) + 1,
            low=Decimal(open_) - 1,
            close=Decimal(close),
            volume=10_000,
            is_complete=True,
        )
    )


class TestCaDetector:
    async def test_split_gap_flags_and_quarantines(self, db: AsyncSession) -> None:
        split = await make_stock(db, symbol="CASPLIT", is_nifty50=True)
        normal = await make_stock(db, symbol="CANORM", is_nifty50=True)
        prev = SESSION - timedelta(days=1)
        # CASPLIT: 1:2 split — close 1000, next open 500 (−50%)
        await _candle(db, split.id, prev, "990", "1000")
        await _candle(db, split.id, SESSION, "500", "505")
        # CANORM: ordinary +1.5% gap
        await _candle(db, normal.id, prev, "99", "100")
        await _candle(db, normal.id, SESSION, "101.5", "102")
        await db.commit()

        flagged = await scan_for_discontinuities(db, SESSION)
        assert [sid for sid, _ in flagged] == [split.id]

        await db.refresh(split)
        assert split.ca_flagged_at is not None
        assert "possible corporate action" in (split.ca_flag_reason or "")
        await db.refresh(normal)
        assert normal.ca_flagged_at is None

        # quarantined → excluded from every universe kind
        ids, _ = await resolve_universe(db, {"kind": "index", "value": "NIFTY50"})
        assert split.id not in ids
        assert normal.id in ids

    async def test_already_flagged_not_reflagged(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="CAONCE")
        prev = SESSION - timedelta(days=1)
        await _candle(db, stock.id, prev, "990", "1000")
        await _candle(db, stock.id, SESSION, "500", "505")
        await db.commit()

        first = await scan_for_discontinuities(db, SESSION)
        assert len(first) == 1
        second = await scan_for_discontinuities(db, SESSION)
        assert second == []

    async def test_no_history_no_flag(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="CANEW")
        await _candle(db, stock.id, SESSION, "100", "101")  # first-ever session
        await db.commit()
        assert await scan_for_discontinuities(db, SESSION) == []
