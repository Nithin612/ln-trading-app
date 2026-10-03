"""A4 — `GET /calendar/constraints`: what is legal NOW, queryable before any submit (Bucket C #4).

The canary: the top-bar banner computed OPEN/CLOSED from the browser clock with a weekday rule,
so it read OPEN on a weekday holiday and CLOSED through a weekend session. Every answer here
comes from its owner — the calendar, `compute_validity_until`, the user, the candle tables.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.models.market_calendar import NseHoliday, NseSpecialSession
from app.models.market_data import OhlcvDaily
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_IST = ZoneInfo("Asia/Kolkata")
WED, THU, SAT, MON = date(2027, 3, 3), date(2027, 3, 4), date(2027, 3, 6), date(2027, 3, 8)


def _ist(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=_IST).astimezone(UTC)


def _iso(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


async def _get(client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
               at: datetime, email: str = "a4@example.com") -> dict[str, Any]:
    monkeypatch.setattr("app.api.v1.calendar._now", lambda: at)
    await create_test_user(db, email=email)
    r = await client.get("/api/v1/calendar/constraints",
                         headers=await get_auth_headers(client, email=email))
    assert r.status_code == 200, r.text
    return r.json()


def _dt(s: str | None) -> datetime | None:
    return None if s is None else datetime.fromisoformat(s).astimezone(UTC)


class TestTheSession:
    async def test_before_the_open_on_a_regular_day(self, client: AsyncClient, db: AsyncSession,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
        s = (await _get(client, db, monkeypatch, _ist(WED, 9, 0)))["session"]
        assert s["today_ist"] == "2027-03-03"
        assert s["is_trading_day"] and s["is_regular_session"] and not s["in_session"]
        assert (s["open_ist"], s["close_ist"]) == ("09:15:00", "15:30:00")
        assert _dt(s["next_open"]) == _ist(WED, 9, 15)
        assert _dt(s["session_close"]) == _ist(WED, 15, 30)

    async def test_inside_the_session(self, client: AsyncClient, db: AsyncSession,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
        s = (await _get(client, db, monkeypatch, _ist(WED, 11, 0)))["session"]
        assert s["in_session"] and s["next_open"] is None
        assert _dt(s["session_close"]) == _ist(WED, 15, 30)

    async def test_after_the_close_points_at_tomorrow(self, client: AsyncClient,
                                                      db: AsyncSession,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
        s = (await _get(client, db, monkeypatch, _ist(WED, 16, 0)))["session"]
        assert not s["in_session"] and s["session_close"] is None
        assert _dt(s["next_open"]) == _ist(THU, 9, 15)

    async def test_an_ordinary_weekend_points_at_monday(self, client: AsyncClient,
                                                        db: AsyncSession,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
        s = (await _get(client, db, monkeypatch, _ist(SAT, 11, 0)))["session"]
        assert not s["is_trading_day"] and not s["in_session"]
        assert s["open_ist"] is None and _dt(s["next_open"]) == _ist(MON, 9, 15)

    async def test_a_weekday_holiday_is_closed(self, client: AsyncClient, db: AsyncSession,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
        """test_banner_reads_open_on_a_holiday: the canary for the banner's weekday rule."""
        db.add(NseHoliday(holiday_date=WED, name="test holiday", source="published"))
        await db.commit()
        s = (await _get(client, db, monkeypatch, _ist(WED, 11, 0)))["session"]
        assert not s["is_trading_day"] and not s["in_session"]
        assert _dt(s["next_open"]) == _ist(THU, 9, 15)

    async def test_a_weekend_special_session_with_its_own_hours(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db.add(NseSpecialSession(session_date=SAT, name="muhurat", source="published",
                                 open_ist=time(18, 0), close_ist=time(19, 0)))
        await db.commit()
        s = (await _get(client, db, monkeypatch, _ist(SAT, 18, 30)))["session"]
        assert s["is_trading_day"] and not s["is_regular_session"] and s["in_session"]
        assert (s["open_ist"], s["close_ist"]) == ("18:00:00", "19:00:00")


class TestValidityOffMarketAndData:
    async def test_validity_comes_from_the_generation_path(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        at = _ist(WED, 11, 0)
        v = {x["classification"]: x
             for x in (await _get(client, db, monkeypatch, at))["validity"]}
        assert set(v) == {"scalp", "intraday", "swing", "positional"}
        assert _dt(v["scalp"]["valid_until"]) == at + timedelta(minutes=30)
        assert _dt(v["intraday"]["valid_until"]) == _ist(WED, 15, 15)
        # 5 trading days after Wed (no holidays seeded) = the next Wednesday, same time
        assert _dt(v["swing"]["valid_until"]) == _ist(date(2027, 3, 10), 11, 0)
        assert "trading days" in v["positional"]["rule"]

    async def test_offmarket_flag_is_the_users(self, client: AsyncClient, db: AsyncSession,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
        from app.models.user import User
        from sqlalchemy import update

        monkeypatch.setattr("app.api.v1.calendar._now", lambda: _ist(WED, 11, 0))
        await create_test_user(db, email="a4b@example.com")
        await db.execute(update(User).where(User.email == "a4b@example.com")
                         .values(allow_offmarket_entry=False))
        await db.commit()
        r = await client.get("/api/v1/calendar/constraints",
                             headers=await get_auth_headers(client, email="a4b@example.com"))
        body = r.json()
        assert body["offmarket_entry_allowed"] is False
        assert "refused" in body["offmarket_rule"]

    async def test_data_limits_report_each_timeframe_and_null_when_empty(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        s = await make_stock(db, symbol="DLIM")
        for d in (date(2027, 1, 4), date(2027, 2, 26)):
            db.add(OhlcvDaily(time=datetime(d.year, d.month, d.day, tzinfo=UTC), stock_id=s.id,
                              open=Decimal("1"), high=Decimal("1"), low=Decimal("1"),
                              close=Decimal("1"), volume=1))
        await db.commit()
        lim = {x["timeframe"]: x
               for x in (await _get(client, db, monkeypatch, _ist(WED, 11, 0)))["data_limits"]}
        assert set(lim) == {"1m", "5m", "15m", "1h", "1d"}
        assert _dt(lim["1d"]["earliest"]) == datetime(2027, 1, 4, tzinfo=UTC)
        assert _dt(lim["1d"]["latest"]) == datetime(2027, 2, 26, tzinfo=UTC)
        assert lim["1m"]["earliest"] is None and lim["1m"]["latest"] is None

    async def test_requires_a_user(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/calendar/constraints")).status_code in (401, 403)


async def test_the_pill_can_skip_the_data_limit_scans(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The top-bar pill polls every 5 minutes from every tab and needs only the session — a
    min/max scan per candle table on each poll is wasted (ui-reviewer, 2026-10-03)."""
    monkeypatch.setattr("app.api.v1.calendar._now", lambda: _ist(WED, 11, 0))
    await create_test_user(db, email="a4c@example.com")
    r = await client.get("/api/v1/calendar/constraints?data_limits=false",
                         headers=await get_auth_headers(client, email="a4c@example.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["data_limits"] == [] and body["session"]["in_session"] is True
