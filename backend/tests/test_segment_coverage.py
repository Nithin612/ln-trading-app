"""U4″ — coverage of the sets whose membership we KNOW.

⛔ **The gap this closes, measured.** U4′ is an unweighted count against a trailing median
— the right shape for the whole archive, whose membership drifts. But its threshold is a
fraction of ~2,637 names, so **~264 must vanish before anything fires**, while the 50
active Nifty-50 constituents are **1.90%** of the archive and all 210 F&O underlyings
**7.96%**. An ingestion bug that drops every blue chip fires NOTHING, and the V1 funnel is
blind too because those names stay `is_active`.

⭐⭐ **A segment needs no baseline, because its denominator is a membership.** Measured
over 20 sessions, both named segments price **100.0% every session** — min, median and max
all 100 — against 97.0% minimum for the whole universe. So the noise floor is literally
zero and ANY absence is the alarm.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.market_data import OhlcvDaily
from app.models.stock import Stock
from app.services.feed_health import (
    SEGMENT_MAX_ABSENT,
    SegmentCoverage,
    check_feed_coverage,
    check_segment_coverage,
    render_feed_coverage,
    render_segment_coverage,
    segments_to_notification,
)
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

SESSION = date(2026, 9, 11)


async def _stock(db: AsyncSession, symbol: str, **flags: bool) -> Stock:
    return await make_stock(db, symbol=symbol, is_active=True, **flags)


async def _bars(db: AsyncSession, stock_ids: list[int], days: list[date]) -> None:
    payload = [
        {"time": datetime(d.year, d.month, d.day, tzinfo=UTC), "stock_id": sid,
         "open": Decimal("100"), "high": Decimal("101"), "low": Decimal("99"),
         "close": Decimal("100"), "volume": 1000, "is_complete": True}
        for d in days for sid in stock_ids
    ]
    if payload:
        await db.execute(insert(OhlcvDaily), payload)


def _seg(rows: list, name: str):  # type: ignore[no-untyped-def]
    return next(r for r in rows if r.name == name)


class TestTheGapU4PrimeCannotSee:
    async def test_a_whole_index_going_dark_fires_here_and_is_silent_there(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ THE ACCEPTANCE TEST, and it asserts BOTH instruments on ONE fixture — the
        `instrument_self_validation` shape. 50 index names vanish out of ~1,000 archive
        names: that is 5%, under U4′'s 10% floor, so the archive alarm stays SILENT while
        this one names every missing constituent."""
        index_names = [await _stock(db, f"NIFTY{i:03d}", is_nifty50=True) for i in range(50)]
        rest = [await _stock(db, f"REST{i:04d}") for i in range(950)]
        prior = [SESSION - timedelta(days=d) for d in range(1, 15)]
        all_ids = [s.id for s in index_names + rest]
        await _bars(db, all_ids, prior)
        # Latest session: everything EXCEPT the index constituents.
        await _bars(db, [s.id for s in rest], [SESSION])
        await db.commit()

        # ⛔ U4′ — 950 of 1,000 is a 5% shortfall, under its 10% floor. Silent.
        archive = next(r for r in await check_feed_coverage(db) if r.table == "ohlcv_1d")
        assert archive.names == 950 and archive.baseline == 1000
        assert archive.shortfall_pct == 5.0
        assert archive.is_collapsed is False
        assert "FEED COVERAGE ALARM" not in "\n".join(render_feed_coverage([archive]))

        # ✅ U4″ — the membership is known, so the absence is exact.
        seg = _seg(await check_segment_coverage(db), "Nifty 50")
        assert seg.expected == 50 and seg.priced == 0
        assert seg.absent_count == 50 and seg.is_collapsed
        md = "\n".join(render_segment_coverage([seg]))
        assert "SEGMENT COVERAGE GAP" in md and "0/50" in md
        assert "NIFTY000" in md  # the NAMES are the actionable part

    async def test_one_missing_constituent_is_already_an_alarm(
        self, db: AsyncSession
    ) -> None:
        """⚠ No tolerance, and that is measured rather than chosen: these sets price
        completely on every one of the last 20 sessions, so one absence is abnormal."""
        members = [await _stock(db, f"NIFTY{i:03d}", is_nifty50=True) for i in range(10)]
        await _bars(db, [s.id for s in members], [SESSION - timedelta(days=1)])
        await _bars(db, [s.id for s in members[1:]], [SESSION])
        await db.commit()

        seg = _seg(await check_segment_coverage(db), "Nifty 50")
        assert SEGMENT_MAX_ABSENT == 0
        assert seg.absent_count == 1 and seg.is_collapsed
        assert seg.absent == ("NIFTY000",)

    async def test_a_complete_segment_is_quiet(self, db: AsyncSession) -> None:
        """The canary: without it, an alarm that fires on every book passes the two above."""
        members = [await _stock(db, f"NIFTY{i:03d}", is_nifty50=True) for i in range(10)]
        await _bars(db, [s.id for s in members], [SESSION])
        await db.commit()
        seg = _seg(await check_segment_coverage(db), "Nifty 50")
        assert seg.priced == 10 and not seg.is_collapsed
        assert seg.coverage_pct == 100.0
        assert "Segment coverage complete" in "\n".join(render_segment_coverage([seg]))
        assert segments_to_notification([seg]) is None


class TestTheHeldSegment:
    async def test_a_held_name_with_no_bar_is_an_alarm(self, db: AsyncSession) -> None:
        """⭐ The money segment. A held name with no bar cannot be MARKED or honestly
        exited — `close_position` falls back to a stale close, then to the entry price
        itself. And it is not a curated list: it is whatever we happen to hold, which is
        exactly why no static configuration would have covered it."""
        user = await create_test_user(db)
        held = await _stock(db, "HELD")
        other = await _stock(db, "OTHER")
        await _bars(db, [held.id, other.id], [SESSION - timedelta(days=1)])
        await _bars(db, [other.id], [SESSION])  # the held name goes dark
        from app.models.trading import Position

        db.add(
            Position(
                user_id=user.id, stock_id=held.id, mode="paper", side="LONG", quantity=10,
                avg_entry_price=Decimal("100"), opened_at=datetime.now(tz=UTC),
            )
        )
        await db.commit()

        seg = _seg(await check_segment_coverage(db), "Open positions")
        assert seg.expected == 1 and seg.priced == 0 and seg.is_collapsed
        assert seg.absent == ("HELD",)
        n = segments_to_notification([seg])
        assert n is not None and n.event == "segment_coverage"
        assert "HELD" in n.render() and "REMEDY" in n.render()

    async def test_a_closed_position_is_not_held(self, db: AsyncSession) -> None:
        """A canary on the membership query itself: a closed position must drop out, or
        every name ever traded would be demanded forever."""
        user = await create_test_user(db)
        gone = await _stock(db, "GONE")
        live = await _stock(db, "LIVE")
        await _bars(db, [live.id], [SESSION])
        from app.models.trading import Position

        db.add(
            Position(
                user_id=user.id, stock_id=gone.id, mode="paper", side="LONG", quantity=10,
                avg_entry_price=Decimal("100"), opened_at=datetime.now(tz=UTC),
                closed_at=datetime.now(tz=UTC),
            )
        )
        await db.commit()
        seg = _seg(await check_segment_coverage(db), "Open positions")
        assert seg.expected == 0 and not seg.is_collapsed


class TestNotAssessable:
    async def test_an_empty_segment_says_nothing_to_check_not_complete(
        self, db: AsyncSession
    ) -> None:
        """⚠ A24. Holding no positions is normal, and it must not render as a green tick
        — "nothing to check" and "checked and fine" are different claims."""
        await _stock(db, "AAA")
        await db.commit()
        seg = _seg(await check_segment_coverage(db), "Open positions")
        assert seg.expected == 0 and not seg.is_measurable
        assert seg.coverage_pct is None
        md = "\n".join(render_segment_coverage([seg]))
        assert "nothing to check" in md and "complete" not in md

    async def test_a_failing_probe_degrades_to_not_assessable(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.feed_health as fh

        monkeypatch.setattr(fh, "_SEGMENT_SQL", "SELECT * FROM nonexistent_table_xyz")
        rows = await check_segment_coverage(db)  # must not raise
        assert rows and all(not r.is_measurable for r in rows)
        assert all(not r.is_collapsed for r in rows)  # unknown, never green

    async def test_segments_render_independently(self, db: AsyncSession) -> None:
        """A gap in one segment must not hide a healthy verdict for another — the A24
        failure U4′ was caught making (bug-hunter, 2026-09-14)."""
        bad = SegmentCoverage("Nifty 50", 50, 10, ("X",), SESSION, 0)
        good = SegmentCoverage("F&O underlyings", 210, 210, (), SESSION, 0)
        md = "\n".join(render_segment_coverage([bad, good]))
        assert "SEGMENT COVERAGE GAP" in md and "Nifty 50" in md
