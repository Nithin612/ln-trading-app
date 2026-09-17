"""The THIRD feed question: a feed can be CURRENT and hold almost nothing.

⛔⛔ **This was a hole between my own instruments, and it took a real outage to find.**
Measured 2026-09-17: `fii_dii_daily` held **5 sessions of roughly 790** — 40 of the last
45 trading days absent — and read **GREEN on every alarm this project owns**:

  · 6.8.6 staleness  — the latest row IS today's, so "current" is true and it says so;
  · U4′ coverage     — excluded by design, the feed has no name dimension to count;
  · U4″ segments     — not applicable, there is no membership;
  · V6 starvation    — excluded on the grounds that "feed_health owns this table".

Each exclusion was individually correct. Their union was a blind spot.

⭐ The missing question is neither recency nor breadth: **how many of the sessions we
should have, do we have.**
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.models.fo_data import FoBhavcopy, IndiaVixDaily
from app.models.market_data import FiiDiiDaily, OhlcvDaily
from app.services.feed_health import (
    COMPLETENESS_MAX_ABSENT,
    check_feed_staleness,
    check_session_completeness,
    completeness_to_notification,
    render_feed_health,
    render_session_completeness,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

_IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 9, 17, 20, 0, tzinfo=_IST)


def _weekdays(count: int, *, end: date) -> list[date]:
    out: list[date] = []
    d = end
    while len(out) < count:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


async def _fii(db: AsyncSession, days: list[date]) -> None:
    for d in days:
        db.add(
            FiiDiiDaily(
                trade_date=d, investor_type="FII", segment="cash",
                buy_value_cr=Decimal("100"), sell_value_cr=Decimal("90"),
            )
        )


def _by(rows: list, table: str):  # type: ignore[no-untyped-def,type-arg]
    return next(r for r in rows if r.table == table)


class TestTheGapBetweenTheOtherAlarms:
    async def test_a_current_but_nearly_empty_feed_is_caught_here_and_nowhere_else(
        self, db: AsyncSession
    ) -> None:
        """⭐ THE ACCEPTANCE TEST, asserting BOTH silences on one fixture — the
        `instrument_self_validation` shape. Today's row is present, so staleness is
        genuinely and correctly quiet; only completeness sees the hole."""
        sessions = _weekdays(30, end=date(2026, 9, 17))
        await _fii(db, [sessions[-1]])  # ONLY today
        # The other EOD feeds stay current, so the staleness header reads green in FULL.
        # A partially-seeded fixture would alarm for an unrelated reason and the
        # reproduction would prove nothing (the same trap U4′'s acceptance test hit).
        stock = await make_stock(db, symbol="SEEDCO")
        db.add(OhlcvDaily(
            time=datetime(2026, 9, 17, tzinfo=UTC), stock_id=stock.id,
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
            close=Decimal("100"), volume=1000, is_complete=True))
        db.add(FoBhavcopy(trade_date=sessions[-1], symbol="NIFTY", instrument="FUT",
                          expiry_date=sessions[-1], strike=Decimal("0")))
        await db.commit()

        # ⛔ Staleness: correct, and blind. The latest row IS the expected session.
        stale = await check_feed_staleness(db, now=NOW)
        assert all(not r.is_stale for r in stale)
        header = "\n".join(render_feed_health(stale))
        assert "Feeds current" in header and "STALENESS ALARM" not in header

        # ✅ Completeness: 1 of 30.
        sc = _by(await check_session_completeness(db, now=NOW), "fii_dii_daily")
        assert sc.present == 1 and sc.expected == 30
        assert sc.is_incomplete and sc.completeness_pct is not None
        md = "\n".join(render_session_completeness([sc]))
        assert "SESSION GAP" in md and "1/30" in md

    async def test_a_complete_feed_is_quiet(self, db: AsyncSession) -> None:
        """The canary: without it, an alarm that fires on everything passes the above."""
        for d in _weekdays(30, end=date(2026, 9, 17)):
            db.add(IndiaVixDaily(trade_date=d, open=Decimal("12"), high=Decimal("13"),
                                 low=Decimal("11"), close=Decimal("12.5")))
        await db.commit()
        sc = _by(await check_session_completeness(db, now=NOW), "india_vix_daily")
        assert sc.present == 30 and not sc.is_incomplete
        assert sc.completeness_pct == 100.0
        assert "Session history complete" in "\n".join(render_session_completeness([sc]))
        assert completeness_to_notification([sc]) is None

    async def test_a_few_missing_sessions_do_not_alarm(self, db: AsyncSession) -> None:
        """⚠ The tolerance is NOT zero. A capture-as-you-go feed legitimately misses the
        odd day — a worker restart, a late publication — and an alarm that fires on one
        is an alarm nobody reads."""
        sessions = _weekdays(30, end=date(2026, 9, 17))
        await _fii(db, sessions[COMPLETENESS_MAX_ABSENT:])  # exactly the tolerance
        await db.commit()
        sc = _by(await check_session_completeness(db, now=NOW), "fii_dii_daily")
        assert sc.absent_count == COMPLETENESS_MAX_ABSENT
        assert not sc.is_incomplete
        # …and one more absence tips it.
        assert COMPLETENESS_MAX_ABSENT == 3


class TestTheRemedyDependsOnTheSource:
    async def test_an_unbackfillable_gap_does_not_send_you_to_a_backfill(
        self, db: AsyncSession
    ) -> None:
        """⛔ The NSE FII/DII endpoint serves ONLY the latest day — re-verified
        2026-09-17, it returned exactly 2 records for one date. A session the worker
        misses is gone from that source forever, so telling a reader to "run the
        backfill" would send them to a script that cannot help. The remedy is keeping the
        worker up."""
        await _fii(db, [date(2026, 9, 17)])
        await db.commit()
        sc = _by(await check_session_completeness(db, now=NOW), "fii_dii_daily")
        assert sc.backfillable is False
        md = "\n".join(render_session_completeness([sc]))
        assert "NOT back-fillable" in md and "gone for good" in md
        assert "REMEDY: back-fill" not in md

        n = completeness_to_notification([sc])
        assert n is not None and n.event == "session_gap"
        assert "NOT backfillable" in n.render()

    async def test_a_backfillable_gap_says_so(self, db: AsyncSession) -> None:
        db.add(IndiaVixDaily(trade_date=date(2026, 9, 17), open=Decimal("12"),
                             high=Decimal("13"), low=Decimal("11"), close=Decimal("12.5")))
        await db.commit()
        sc = _by(await check_session_completeness(db, now=NOW), "india_vix_daily")
        assert sc.backfillable is True
        assert "back-fill the missing dates" in "\n".join(render_session_completeness([sc]))


class TestItCountsSESSIONS:
    async def test_weekends_are_not_missing_sessions(self, db: AsyncSession) -> None:
        """⚠ The trading calendar owns which days SHOULD exist. Counting calendar days
        would read every weekend as an outage and the channel would be ignored in a
        fortnight."""
        sc = _by(await check_session_completeness(db, now=NOW), "fii_dii_daily")
        assert all(d.weekday() < 5 for d in sc.missing)


class TestProbeNeverRaises:
    async def test_a_failing_probe_degrades_to_unmeasurable(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def boom(*_a: object, **_k: object) -> list[date]:
            raise RuntimeError("calendar unavailable")

        monkeypatch.setattr("app.services.feed_health.trading_days_between", boom)
        rows = await check_session_completeness(db, now=NOW)  # must not raise
        assert rows and all(not r.is_measurable for r in rows)
        assert all(not r.is_incomplete for r in rows)  # unknown, never alarmed
        assert completeness_to_notification(rows) is None
