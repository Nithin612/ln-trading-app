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


class TestDetectionIsNotGatedOnTradeability:
    """D4a (2026-09-13) — REGRESSION: the detector was gated on `s.is_active`.

    A corporate action is a fact about a PRICE SERIES, not about whether we
    currently trade the name. Gating detection on the trading flag was redundant
    (the quarantine's only consumer, `resolve_universe`, filters `is_active`
    itself) and actively harmful: between 2026-09-07 and 09-12 the real universe
    was wrongly `is_active = false`, so the detector was blind to exactly the
    names that mattered. It has produced 3 flags in its lifetime, against 49
    unadjusted actions known to sit in the top-250-liquid set alone.

    These fail on the old code, which skipped inactive stocks entirely.
    """

    async def test_an_inactive_stock_is_still_flagged(self, db: AsyncSession) -> None:
        dormant = await make_stock(db, symbol="CAINACT", is_active=False)
        prev = SESSION - timedelta(days=1)
        await _candle(db, dormant.id, prev, "990", "1000")
        await _candle(db, dormant.id, SESSION, "500", "505")  # 1:2 split
        await db.commit()

        flagged = await scan_for_discontinuities(db, SESSION)

        assert [sid for sid, _ in flagged] == [dormant.id]
        await db.refresh(dormant)
        assert dormant.ca_flagged_at is not None

    async def test_active_and_inactive_are_both_caught_in_one_pass(
        self, db: AsyncSession
    ) -> None:
        live = await make_stock(db, symbol="CALIVE", is_active=True)
        dormant = await make_stock(db, symbol="CADEAD", is_active=False)
        prev = SESSION - timedelta(days=1)
        for s in (live, dormant):
            await _candle(db, s.id, prev, "990", "1000")
            await _candle(db, s.id, SESSION, "500", "505")
        await db.commit()

        flagged = {sid for sid, _ in await scan_for_discontinuities(db, SESSION)}

        assert flagged == {live.id, dormant.id}  # old code: {live.id}

    async def test_an_already_flagged_stock_is_not_reflagged(
        self, db: AsyncSession
    ) -> None:
        """The idempotency guard must survive the ungating — otherwise every
        session would rewrite the reason and lose the original one."""
        s = await make_stock(db, symbol="CAONCE", is_active=False)
        prev = SESSION - timedelta(days=1)
        await _candle(db, s.id, prev, "990", "1000")
        await _candle(db, s.id, SESSION, "500", "505")
        await db.commit()

        first = await scan_for_discontinuities(db, SESSION)
        assert len(first) == 1
        assert await scan_for_discontinuities(db, SESSION) == []
