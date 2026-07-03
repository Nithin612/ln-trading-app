"""Unit tests for the event guard — Phase 6."""

from datetime import UTC, datetime, timedelta

from app.models.filing import CorporateFiling
from app.signals.event_guard import is_signal_suppressed
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


async def _make_filing(
    db: AsyncSession,
    stock_id: int,
    filing_type: str = "earnings",
    minutes_ago: int = 10,
    source: str = "NSE",
) -> CorporateFiling:
    filing_time = datetime.now(tz=UTC) - timedelta(minutes=minutes_ago)
    filing = CorporateFiling(
        stock_id=stock_id,
        filing_type=filing_type,
        headline=f"Test {filing_type} filing",
        filing_date=filing_time.date(),
        filing_time=filing_time,
        source=source,
    )
    db.add(filing)
    await db.flush()
    return filing


class TestEventGuard:
    async def test_no_filings_not_suppressed(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="CLEAN")
        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is False
        assert result.reason is None
        assert result.suppressed_until is None

    async def test_earnings_within_1h_suppresses(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="EARCO")
        await _make_filing(db, stock.id, filing_type="earnings", minutes_ago=30)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is True
        assert "earnings" in result.reason
        assert result.suppressed_until is not None

    async def test_merger_within_1h_suppresses(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="MERCO")
        await _make_filing(db, stock.id, filing_type="merger", minutes_ago=15)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is True

    async def test_rating_change_within_1h_suppresses(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="RATCO")
        await _make_filing(db, stock.id, filing_type="rating_change", minutes_ago=45)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is True

    async def test_earnings_older_than_1h_not_suppressed(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="OLDCO")
        await _make_filing(db, stock.id, filing_type="earnings", minutes_ago=90)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is False

    async def test_low_impact_filing_does_not_suppress(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="LOWCO")
        await _make_filing(db, stock.id, filing_type="board_meeting", minutes_ago=5)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is False

    async def test_other_stock_filing_does_not_affect_this_stock(self, db: AsyncSession) -> None:
        stock_a = await make_stock(db, symbol="STOCA")
        stock_b = await make_stock(db, symbol="STOCB", isin="INE999Z99999")
        await _make_filing(db, stock_b.id, filing_type="earnings", minutes_ago=5)
        await db.commit()

        result = await is_signal_suppressed(db, stock_a.id)
        assert result.suppressed is False

    async def test_reason_contains_minutes_ago(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="TIMCO")
        await _make_filing(db, stock.id, filing_type="earnings", minutes_ago=23)
        await db.commit()

        result = await is_signal_suppressed(db, stock.id)
        assert result.suppressed is True
        assert "23" in result.reason
