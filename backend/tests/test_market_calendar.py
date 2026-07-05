"""Market calendar service + API (Phase 2 slice 1).

Trading-day arithmetic must respect weekends AND nse_holidays rows —
calendar-day approximations are the bug this slice removes
(SIGNAL_ENGINE.md §5: swing 5 / positional 30 TRADING days).
"""

from datetime import UTC, date, datetime

import pytest
from app.models.market_calendar import NseHoliday
from app.services import market_calendar
from app.signals.expiry import compute_validity_until
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers


async def _seed(db: AsyncSession, *dates_names: tuple[date, str]) -> None:
    for d, name in dates_names:
        db.add(NseHoliday(holiday_date=d, name=name, source="published"))
    await db.commit()


# Real NSE closures used as fixtures (derived from bhavcopy ground truth):
DIWALI_2025 = date(2025, 10, 22)  # Wednesday — Balipratipada
GANDHI_2025 = date(2025, 10, 2)  # Thursday


class TestTradingDayArithmetic:
    async def test_weekends_never_trade(self, db: AsyncSession) -> None:
        assert not await market_calendar.is_trading_day(db, date(2025, 10, 25))  # Sat
        assert not await market_calendar.is_trading_day(db, date(2025, 10, 26))  # Sun

    async def test_holiday_not_a_trading_day(self, db: AsyncSession) -> None:
        await _seed(db, (DIWALI_2025, "Diwali Balipratipada"))
        assert not await market_calendar.is_trading_day(db, DIWALI_2025)
        assert await market_calendar.is_trading_day(db, date(2025, 10, 21))

    async def test_add_trading_days_skips_weekend_and_holiday(
        self, db: AsyncSession
    ) -> None:
        await _seed(db, (DIWALI_2025, "Diwali Balipratipada"))
        # Fri 2025-10-17 + 5 trading days: 20, 21, 23, 24, 27 (22nd is
        # Diwali, 18/19 + 25/26 are weekends) → Mon 2025-10-27
        start = datetime(2025, 10, 17, 12, 30, tzinfo=UTC)
        out = await market_calendar.add_trading_days(db, start, 5)
        assert out.date() == date(2025, 10, 27)
        assert out.timetz() == start.timetz()  # same wall time preserved

    async def test_add_trading_days_plain_week(self, db: AsyncSession) -> None:
        # Mon 2025-11-10 + 5 trading days with no holidays → Mon 2025-11-17
        start = datetime(2025, 11, 10, 6, 0, tzinfo=UTC)
        out = await market_calendar.add_trading_days(db, start, 5)
        assert out.date() == date(2025, 11, 17)

    async def test_next_prev_trading_day(self, db: AsyncSession) -> None:
        await _seed(db, (GANDHI_2025, "Gandhi Jayanti"))
        # Wed Oct 1 → next is Fri Oct 3 (Thu is Gandhi Jayanti)
        assert await market_calendar.next_trading_day(db, date(2025, 10, 1)) == date(2025, 10, 3)
        # Fri Oct 3 → prev is Wed Oct 1
        assert await market_calendar.prev_trading_day(db, date(2025, 10, 3)) == date(2025, 10, 1)

    async def test_last_n_trading_days(self, db: AsyncSession) -> None:
        await _seed(db, (GANDHI_2025, "Gandhi Jayanti"))
        # ending Mon Oct 6: [Sep 29, 30, Oct 1, 3, 6] — skips Gandhi + weekend
        days = await market_calendar.last_n_trading_days(db, date(2025, 10, 6), 5)
        assert days == [
            date(2025, 9, 29),
            date(2025, 9, 30),
            date(2025, 10, 1),
            date(2025, 10, 3),
            date(2025, 10, 6),
        ]

    async def test_rejects_nonpositive_n(self, db: AsyncSession) -> None:
        with pytest.raises(ValueError):
            await market_calendar.add_trading_days(db, datetime.now(tz=UTC), 0)


class TestValidityOffset:
    """Regression: swing/positional validity used 7/42 CALENDAR days —
    holiday clusters made signals expire early (and plain weeks late)."""

    async def test_swing_five_trading_days_over_diwali(self, db: AsyncSession) -> None:
        await _seed(db, (DIWALI_2025, "Diwali Balipratipada"))
        created = datetime(2025, 10, 17, 13, 0, tzinfo=UTC)  # Friday
        offset = await market_calendar.validity_offset_days(db, "swing", created)
        # Fri → Mon Oct 27 = 10 calendar days (NOT the old flat 7)
        assert offset == 10
        validity = compute_validity_until("swing", created, trading_days_offset=offset)
        assert validity.date() == date(2025, 10, 27)

    async def test_swing_plain_week_is_seven_calendar_days(self, db: AsyncSession) -> None:
        created = datetime(2025, 11, 10, 13, 0, tzinfo=UTC)  # Monday, no holidays
        offset = await market_calendar.validity_offset_days(db, "swing", created)
        assert offset == 7  # Mon → next Mon

    async def test_non_trading_day_classifications_unaffected(
        self, db: AsyncSession
    ) -> None:
        created = datetime(2025, 11, 10, 13, 0, tzinfo=UTC)
        assert await market_calendar.validity_offset_days(db, "scalp", created) == 0
        assert await market_calendar.validity_offset_days(db, "intraday", created) == 0


class TestCalendarApi:
    async def test_add_list_delete_roundtrip(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db, email="cal-admin@example.com", role="admin")
        headers = await get_auth_headers(client, email="cal-admin@example.com")

        r = await client.post(
            "/api/v1/calendar/holidays",
            json={"holiday_date": "2027-01-26", "name": "Republic Day"},
            headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["source"] == "manual"

        r = await client.get("/api/v1/calendar/holidays?year=2027", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["holidays"][0]["holiday_date"] == "2027-01-26"
        assert body["coverage_end"] == "2027-01-26"

        r = await client.delete("/api/v1/calendar/holidays/2027-01-26", headers=headers)
        assert r.status_code == 204
        r = await client.get("/api/v1/calendar/holidays?year=2027", headers=headers)
        assert r.json()["total"] == 0

    async def test_weekend_rejected(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db, email="cal-admin2@example.com", role="admin")
        r = await client.post(
            "/api/v1/calendar/holidays",
            json={"holiday_date": "2027-01-24", "name": "Sunday"},  # Sunday
            headers=await get_auth_headers(client, email="cal-admin2@example.com"),
        )
        assert r.status_code == 422

    async def test_duplicate_conflicts(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db, email="cal-admin3@example.com", role="admin")
        headers = await get_auth_headers(client, email="cal-admin3@example.com")
        payload = {"holiday_date": "2027-03-01", "name": "Test"}
        assert (
            await client.post("/api/v1/calendar/holidays", json=payload, headers=headers)
        ).status_code == 201
        assert (
            await client.post("/api/v1/calendar/holidays", json=payload, headers=headers)
        ).status_code == 409

    async def test_add_requires_admin(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db, email="cal-user@example.com")
        r = await client.post(
            "/api/v1/calendar/holidays",
            json={"holiday_date": "2027-04-01", "name": "Nope"},
            headers=await get_auth_headers(client, email="cal-user@example.com"),
        )
        assert r.status_code == 403

    async def test_trading_day_endpoint(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db, email="cal-user2@example.com")
        await _seed(db, (GANDHI_2025, "Gandhi Jayanti"))
        r = await client.get(
            "/api/v1/calendar/trading-day?d=2025-10-02",
            headers=await get_auth_headers(client, email="cal-user2@example.com"),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_trading_day"] is False
        assert body["prev_trading_day"] == "2025-10-01"
        assert body["next_trading_day"] == "2025-10-03"
