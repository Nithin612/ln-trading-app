"""Weekend NSE sessions (Bucket C #1, 2026-10-03).

NSE holds Saturday and Sunday sessions — Union Budget days, DR drills, muhurat trading; the
archive has 8 (2019-10-27 … 2026-02-01). The calendar was "a weekday that is not a holiday", so
`is_trading_day` returned False for every one of them, and 21 Mon–Fri beats never fired on them.
These tests pin the repair at each seam: the calendar predicate, every helper built on it, the
intraday guard, the task guard, the seed and the admin API.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from app.models.market_calendar import NseHoliday, NseSpecialSession
from app.models.market_data import OhlcvDaily
from app.services import market_calendar as mc
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

BUDGET_SAT = date(2025, 2, 1)  # a real Saturday session (Union Budget)
ORDINARY_SAT = date(2025, 2, 8)
FRI_BEFORE, MON_AFTER = date(2025, 1, 31), date(2025, 2, 3)


async def _special(db: AsyncSession, d: date, hours: tuple[time, time] | None = None) -> None:
    db.add(NseSpecialSession(session_date=d, name="test session", source="published",
                             open_ist=hours[0] if hours else None,
                             close_ist=hours[1] if hours else None))
    await db.commit()


def _utc(d: date, hh: int, mm: int) -> datetime:
    """An IST wall-clock moment on `d`, as UTC."""
    from zoneinfo import ZoneInfo

    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC)


class TestTheCalendarPredicate:
    async def test_a_recorded_weekend_session_is_a_trading_day(self, db: AsyncSession) -> None:
        """test_weekend_session_reads_as_closed: the canary — False on the old predicate."""
        await _special(db, BUDGET_SAT)
        assert await mc.is_trading_day(db, BUDGET_SAT) is True

    async def test_an_ordinary_weekend_is_still_closed(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)
        assert await mc.is_trading_day(db, ORDINARY_SAT) is False

    async def test_a_weekday_holiday_is_still_closed(self, db: AsyncSession) -> None:
        db.add(NseHoliday(holiday_date=FRI_BEFORE, name="test holiday", source="published"))
        await db.commit()
        assert await mc.is_trading_day(db, FRI_BEFORE) is False


class TestEveryHelperUsesThePredicate:
    async def test_trading_days_between_includes_the_weekend_session(
        self, db: AsyncSession
    ) -> None:
        await _special(db, BUDGET_SAT)
        got = await mc.trading_days_between(db, FRI_BEFORE, MON_AFTER)
        assert got == [FRI_BEFORE, BUDGET_SAT, MON_AFTER]

    async def test_add_trading_days_counts_it(self, db: AsyncSession) -> None:
        """Validity in TRADING days (SIGNAL_ENGINE §5): a Saturday session is one."""
        await _special(db, BUDGET_SAT)
        start = datetime(2025, 1, 31, 10, 0, tzinfo=UTC)
        assert (await mc.add_trading_days(db, start, 1)).date() == BUDGET_SAT
        assert (await mc.add_trading_days(db, start, 2)).date() == MON_AFTER

    async def test_prev_and_next_and_last_n(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)
        assert await mc.prev_trading_day(db, MON_AFTER) == BUDGET_SAT
        assert await mc.next_trading_day(db, FRI_BEFORE) == BUDGET_SAT
        assert await mc.last_n_trading_days(db, MON_AFTER, 3) == [FRI_BEFORE, BUDGET_SAT,
                                                                   MON_AFTER]


class TestTheIntradayGuard:
    async def test_session_hours(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)
        await _special(db, date(2024, 11, 2), (time(18, 0), time(19, 0)))  # an evening muhurat
        assert await mc.session_hours(db, MON_AFTER) == (time(9, 15), time(15, 30))
        assert await mc.session_hours(db, BUDGET_SAT) == (time(9, 15), time(15, 30))
        assert await mc.session_hours(db, date(2024, 11, 2)) == (time(18, 0), time(19, 0))
        assert await mc.session_hours(db, ORDINARY_SAT) is None

    async def test_in_market_session_follows_the_calendar(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)
        await _special(db, date(2024, 11, 2), (time(18, 0), time(19, 0)))
        assert await mc.in_market_session(db, _utc(BUDGET_SAT, 10, 0)) is True
        assert await mc.in_market_session(db, _utc(ORDINARY_SAT, 10, 0)) is False
        assert await mc.in_market_session(db, _utc(BUDGET_SAT, 16, 0)) is False
        # the muhurat's own hours, not 09:15–15:30
        assert await mc.in_market_session(db, _utc(date(2024, 11, 2), 18, 30)) is True
        assert await mc.in_market_session(db, _utc(date(2024, 11, 2), 10, 0)) is False

    def test_the_pure_fallback_is_unchanged_and_none_means_closed(self) -> None:
        from app.trading.market_hours import is_market_session

        assert is_market_session(_utc(BUDGET_SAT, 10, 0)) is False  # calendar-free: weekday rule
        assert is_market_session(_utc(MON_AFTER, 10, 0)) is True
        assert is_market_session(_utc(BUDGET_SAT, 10, 0), (time(9, 15), time(15, 30))) is True
        assert is_market_session(_utc(MON_AFTER, 10, 0), None) is False

    async def test_skip_unless_trading_day(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)
        assert await mc.skip_unless_trading_day(db, _utc(BUDGET_SAT, 9, 0)) is None
        skip = await mc.skip_unless_trading_day(db, _utc(ORDINARY_SAT, 9, 0))
        assert skip is not None and skip["status"] == "skipped"
        assert str(ORDINARY_SAT) in str(skip["message"])


class TestTheSeed:
    async def test_derives_weekend_sessions_from_the_bhavcopy_idempotently(
        self, db: AsyncSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts import seed_nse_special_sessions as seed

        stock = await make_stock(db, symbol="WKND")
        for d in (FRI_BEFORE, BUDGET_SAT):  # bars on a Friday and on the Saturday session
            db.add(OhlcvDaily(time=datetime(d.year, d.month, d.day, tzinfo=UTC),
                              stock_id=stock.id, open=Decimal("10"), high=Decimal("11"),
                              low=Decimal("9"), close=Decimal("10"), volume=100))
        await db.commit()

        assert await seed.main(dry_run=False) == 0
        rows = (await db.execute(select(NseSpecialSession))).scalars().all()
        assert [r.session_date for r in rows] == [BUDGET_SAT]  # the Friday is not special
        assert rows[0].source == "derived" and rows[0].open_ist is None
        assert await seed.main(dry_run=False) == 0
        assert "0 new row(s)" in capsys.readouterr().out.splitlines()[-1]


class TestTheApi:
    async def test_add_list_delete_and_the_trading_day_endpoint(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db, email="ss-admin@example.com", role="admin")
        h = await get_auth_headers(client, email="ss-admin@example.com")
        body = {"session_date": "2027-02-06", "name": "Budget Saturday"}
        r = await client.post("/api/v1/calendar/special-sessions", json=body, headers=h)
        assert r.status_code == 201 and r.json()["source"] == "manual"
        r = await client.get("/api/v1/calendar/trading-day?d=2027-02-06", headers=h)
        assert r.json()["is_trading_day"] is True
        r = await client.get("/api/v1/calendar/special-sessions", headers=h)
        assert [x["session_date"] for x in r.json()] == ["2027-02-06"]
        assert (await client.post("/api/v1/calendar/special-sessions", json=body,
                                  headers=h)).status_code == 409
        r = await client.delete("/api/v1/calendar/special-sessions/2027-02-06", headers=h)
        assert r.status_code == 204

    @pytest.mark.parametrize("payload", [
        {"session_date": "2027-02-05", "name": "a Friday"},  # a weekday needs no row
        {"session_date": "2027-02-06", "name": "x", "open_ist": "18:00:00"},  # half the hours
        {"session_date": "2027-02-06", "name": "x", "open_ist": "19:00:00",
         "close_ist": "18:00:00"},  # open after close
    ])
    async def test_rejections(self, client: AsyncClient, db: AsyncSession,
                              payload: dict[str, str]) -> None:
        await create_test_user(db, email="ss-admin2@example.com", role="admin")
        h = await get_auth_headers(client, email="ss-admin2@example.com")
        r = await client.post("/api/v1/calendar/special-sessions", json=payload, headers=h)
        assert r.status_code == 422

    async def test_add_requires_admin(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db, email="ss-user@example.com")
        r = await client.post(
            "/api/v1/calendar/special-sessions",
            json={"session_date": "2027-02-06", "name": "x"},
            headers=await get_auth_headers(client, email="ss-user@example.com"),
        )
        assert r.status_code == 403


class TestRegularSessionsOnly:
    """bug-hunter 2026-10-03: jobs built on the regular day's shape (the closing auction, the
    intraday profiles, the post-close EOD file) must skip a special session with other hours."""

    async def test_is_regular_session(self, db: AsyncSession) -> None:
        await _special(db, BUDGET_SAT)  # recorded without hours ⇒ regular
        await _special(db, date(2024, 11, 2), (time(18, 0), time(19, 0)))  # evening muhurat
        assert await mc.is_regular_session(db, MON_AFTER) is True
        assert await mc.is_regular_session(db, BUDGET_SAT) is True
        assert await mc.is_regular_session(db, date(2024, 11, 2)) is False
        assert await mc.is_regular_session(db, ORDINARY_SAT) is False

    async def test_the_cas_absence_alarm_expects_no_auction_on_an_evening_session(
        self, db: AsyncSession
    ) -> None:
        """The capture skips it, so a zero row count there must not read as a MISS."""
        from app.services.worker_health import cas_coverage

        muhurat = date(2024, 11, 2)
        await _special(db, muhurat, (time(18, 0), time(19, 0)))
        cov = await cas_coverage(db, day=muhurat, now=_utc(muhurat, 20, 0))
        assert cov.is_missed is False and cov.postclose_missed is False
        await _special(db, BUDGET_SAT)  # a regular-hours weekend session DOES expect one
        cov = await cas_coverage(db, day=BUDGET_SAT, now=_utc(BUDGET_SAT, 20, 0))
        assert cov.is_missed is True

    def test_the_intraday_beats_cover_an_evening_session(self) -> None:
        import importlib

        from app.celery_app import celery_app

        for mod in celery_app.conf.include:
            importlib.import_module(mod)
        for name, entry in celery_app.conf.beat_schedule.items():
            if entry["task"] in ("app.tasks.position_monitor.monitor_positions",
                                 "app.tasks.fo_tasks.record_option_chains",
                                 "app.tasks.circuit_tasks.refresh_circuit_bands"):
                hours = {int(h) for h in entry["schedule"].hour}
                assert {3, 13, 14} <= hours, name  # 08:30 … 20:29 IST

    async def test_a_weekday_muhurat_can_be_recorded_with_its_hours(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db, email="ss-admin3@example.com", role="admin")
        h = await get_auth_headers(client, email="ss-admin3@example.com")
        r = await client.post("/api/v1/calendar/special-sessions", headers=h, json={
            "session_date": "2027-11-05", "name": "Muhurat", "open_ist": "18:00:00",
            "close_ist": "19:00:00"})  # a Friday
        assert r.status_code == 201
        assert await mc.is_regular_session(db, date(2027, 11, 5)) is False
