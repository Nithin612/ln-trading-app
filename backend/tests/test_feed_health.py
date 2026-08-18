"""Phase 6.8.6 — silent-feed-outage alarm.

Staleness of the EOD feeds (ohlcv_1d, fo_bhavcopy, fii_dii_daily) measured in
TRADING days vs the last completed EOD cycle — a weekend/holiday or a pre-EOD
morning run is not an outage. Dates: 2026-08-10 Mon … 08-14 Fri, 08-15 Sat.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.models.fo_data import FoBhavcopy
from app.models.market_data import FiiDiiDaily, OhlcvDaily
from app.services.daily_report import build_daily_report, render_markdown
from app.services.feed_health import (
    FeedStatus,
    check_feed_staleness,
    render_feed_health,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

_IST = ZoneInfo("Asia/Kolkata")
FRI = date(2026, 8, 14)
# Friday 19:00 IST — past the 18:45 EOD-due cutoff, so today's cycle is expected.
FRI_EVENING = datetime(2026, 8, 14, 19, 0, tzinfo=_IST)


async def _seed_ohlcv_1d(db: AsyncSession, stock_id: int, d: date) -> None:
    db.add(OhlcvDaily(
        time=datetime(d.year, d.month, d.day, tzinfo=UTC), stock_id=stock_id,
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
        volume=1000, is_complete=True,
    ))


async def _seed_fo(db: AsyncSession, d: date) -> None:
    db.add(FoBhavcopy(
        trade_date=d, symbol="NIFTY", instrument="FUT", expiry_date=d, strike=Decimal("0"),
    ))


async def _seed_fii(db: AsyncSession, d: date) -> None:
    db.add(FiiDiiDaily(
        trade_date=d, investor_type="FII", segment="cash",
        buy_value_cr=Decimal("100.00"), sell_value_cr=Decimal("90.00"),
    ))


def _by_table(rows: list[FeedStatus], table: str) -> FeedStatus:
    return next(r for r in rows if r.table == table)


async def _seed_all(db: AsyncSession, stock_id: int, d: date) -> None:
    await _seed_ohlcv_1d(db, stock_id, d)
    await _seed_fo(db, d)
    await _seed_fii(db, d)


class TestFeedStaleness:
    async def test_all_current_is_quiet(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        await _seed_all(db, stock.id, FRI)  # every feed current through Friday
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        assert all(r.days_behind == 0 and not r.is_stale for r in rows)
        assert "Feeds current" in "\n".join(render_feed_health(rows))

    async def test_feed_three_trading_days_stale_alarms(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        # equity EOD stuck at Tue 08-11; the others current → only equity stale
        await _seed_ohlcv_1d(db, stock.id, date(2026, 8, 11))
        await _seed_fo(db, FRI)
        await _seed_fii(db, FRI)
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        equity = _by_table(rows, "ohlcv_1d")
        # Tue→Fri: Wed/Thu/Fri are the 3 missing trading days
        assert equity.days_behind == 3 and equity.is_stale
        assert _by_table(rows, "fo_bhavcopy").days_behind == 0
        assert _by_table(rows, "fii_dii_daily").days_behind == 0
        md = "\n".join(render_feed_health(rows))
        assert "FEED STALENESS ALARM" in md and "3" in md

    async def test_weekend_gap_is_not_an_outage(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        await _seed_all(db, stock.id, FRI)  # data through Friday
        await db.commit()
        # Saturday — no trading; expected falls back to Friday, so nothing is behind
        sat = datetime(2026, 8, 15, 12, 0, tzinfo=_IST)
        rows = await check_feed_staleness(db, now=sat)
        assert all(not r.is_stale for r in rows)

    async def test_pre_eod_morning_does_not_require_today(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        # data only through Thursday; a Friday 09:00 IST run (pre-EOD) must be quiet
        await _seed_all(db, stock.id, date(2026, 8, 13))
        await db.commit()
        fri_morning = datetime(2026, 8, 14, 9, 0, tzinfo=_IST)
        rows = await check_feed_staleness(db, now=fri_morning)
        assert all(not r.is_stale for r in rows)  # today's EOD not due yet

    async def test_empty_feed_is_maximally_stale(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        # only equity seeded; fo + fii are empty → NO DATA → stale
        await _seed_ohlcv_1d(db, stock.id, FRI)
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        fo = _by_table(rows, "fo_bhavcopy")
        assert fo.latest is None and fo.days_behind is None and fo.is_stale
        md = "\n".join(render_feed_health(rows))
        assert "FEED STALENESS ALARM" in md and "NO DATA AT ALL" in md

    async def test_latest_on_a_non_trading_date_is_not_undercounted(
        self, db: AsyncSession
    ) -> None:
        """bug-hunter LOW regression: if a feed's latest row falls on a date that is
        NOT a trading day (a holiday seeded after the row was written), the missing
        trading days after it must still be counted — the old `-1` erased one and
        under-reported the outage in the unsafe direction."""
        from app.models.market_calendar import NseHoliday

        stock = await make_stock(db)
        await _seed_all(db, stock.id, date(2026, 8, 13))  # latest = Thu 08-13
        db.add(NseHoliday(holiday_date=date(2026, 8, 13), name="Late-flagged holiday"))
        await db.commit()
        # expected = Fri 08-14 (FRI_EVENING); only Fri is missing → 1, not 0
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        assert _by_table(rows, "ohlcv_1d").days_behind == 1
        assert all(r.is_stale for r in rows)

    async def test_stale_gap_spanning_a_weekend_counts_trading_days_only(
        self, db: AsyncSession
    ) -> None:
        """Calendar-awareness core (trading-domain: calendar-day arithmetic is a bug).
        Fri 08-07 → Fri 08-14 is 7 CALENDAR days but 5 TRADING days (Sat/Sun skipped)."""
        stock = await make_stock(db)
        await _seed_ohlcv_1d(db, stock.id, date(2026, 8, 7))  # last Friday
        await _seed_fo(db, FRI)
        await _seed_fii(db, FRI)
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        assert _by_table(rows, "ohlcv_1d").days_behind == 5  # Mon–Fri, NOT 7

    async def test_stale_gap_with_a_holiday_inside_is_not_counted(
        self, db: AsyncSession
    ) -> None:
        """A holiday WITHIN the gap is not a missing trading day."""
        from app.models.market_calendar import NseHoliday

        stock = await make_stock(db)
        await _seed_ohlcv_1d(db, stock.id, date(2026, 8, 7))
        await _seed_fo(db, FRI)
        await _seed_fii(db, FRI)
        db.add(NseHoliday(holiday_date=date(2026, 8, 12), name="Mid-gap holiday"))  # a Wed
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        assert _by_table(rows, "ohlcv_1d").days_behind == 4  # 5 minus the holiday

    async def test_eod_due_cutoff_boundary(self, db: AsyncSession) -> None:
        """The 18:45 IST cutoff: before it, today's EOD isn't due (quiet); at/after
        it, today is expected (a missing today alarms)."""
        stock = await make_stock(db)
        await _seed_all(db, stock.id, date(2026, 8, 13))  # data through Thursday only
        await db.commit()
        before = datetime(2026, 8, 14, 18, 44, tzinfo=_IST)
        at = datetime(2026, 8, 14, 18, 45, tzinfo=_IST)
        assert all(not r.is_stale for r in await check_feed_staleness(db, now=before))
        rows_at = await check_feed_staleness(db, now=at)
        assert _by_table(rows_at, "ohlcv_1d").days_behind == 1  # today now due, missing

    async def test_stale_feed_logs_a_warning(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Loud even without the report: a stale feed emits a warning; none when all
        current."""
        stock = await make_stock(db)
        await _seed_ohlcv_1d(db, stock.id, date(2026, 8, 11))  # equity stale
        await _seed_fo(db, FRI)
        await _seed_fii(db, FRI)
        await db.commit()
        with caplog.at_level(logging.WARNING):
            await check_feed_staleness(db, now=FRI_EVENING)
        assert "FEED STALE" in caplog.text and "Equity EOD" in caplog.text

        caplog.clear()
        await _seed_ohlcv_1d(db, stock.id, FRI)  # now current
        await db.commit()
        with caplog.at_level(logging.WARNING):
            await check_feed_staleness(db, now=FRI_EVENING)
        assert "FEED STALE" not in caplog.text

    async def test_render_current_has_no_alarm(self, db: AsyncSession) -> None:
        stock = await make_stock(db)
        await _seed_all(db, stock.id, FRI)
        await db.commit()
        rows = await check_feed_staleness(db, now=FRI_EVENING)
        md = "\n".join(render_feed_health(rows))
        assert "FEED STALENESS ALARM" not in md and "Feeds current" in md


# ── the daily-report seam (build_daily_report → render_markdown) ───────────────
class TestFeedHealthInDailyReport:
    async def test_report_renders_alarm_when_a_feed_is_stale(self, db: AsyncSession) -> None:
        """Integration through the seam: a stale feed surfaces the loud header in the
        actual rendered report (not just the isolated render function)."""
        user = await create_test_user(db)
        await make_stock(db)  # feeds left empty → NO DATA → stale
        await db.commit()
        report = await build_daily_report(db, day=FRI, user_id=user.id, now=FRI_EVENING)
        assert report.feed_health  # wiring populated the field
        assert "FEED STALENESS ALARM" in render_markdown(report)

    async def test_report_renders_quiet_header_when_feeds_current(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _seed_all(db, stock.id, FRI)
        await db.commit()
        report = await build_daily_report(db, day=FRI, user_id=user.id, now=FRI_EVENING)
        md = render_markdown(report)
        assert "Feeds current" in md and "FEED STALENESS ALARM" not in md
