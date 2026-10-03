"""Market-calendar endpoints (Phase 2 slice 1).

GET  /calendar/holidays            — list holidays (optionally by year)
POST /calendar/holidays            — (admin) add a holiday (NSE circular)
DELETE /calendar/holidays/{date}   — (admin) remove a wrong entry
GET  /calendar/special-sessions    — list weekend sessions (Budget / DR drill / muhurat)
POST /calendar/special-sessions    — (admin) add one announced by NSE circular
DELETE /calendar/special-sessions/{date} — (admin) remove a wrong entry
GET  /calendar/trading-day         — is a date a trading day (+ neighbours)
GET  /calendar/constraints         — A4: what is legal NOW, queryable before any submit
"""

from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.market_calendar import NseHoliday, NseSpecialSession
from app.models.user import User
from app.services import market_calendar

router = APIRouter(prefix="/calendar", tags=["calendar"])


class HolidayIn(BaseModel):
    holiday_date: date
    name: str = Field(min_length=1, max_length=128)


class HolidayOut(BaseModel):
    holiday_date: date
    name: str
    source: str

    model_config = {"from_attributes": True}


class SpecialSessionIn(BaseModel):
    session_date: date
    name: str = Field(min_length=1, max_length=128)
    open_ist: time | None = None
    close_ist: time | None = None


class SpecialSessionOut(SpecialSessionIn):
    source: str

    model_config = {"from_attributes": True}


class HolidayListResponse(BaseModel):
    total: int
    coverage_end: date | None
    holidays: list[HolidayOut]


class TradingDayOut(BaseModel):
    for_date: date
    is_trading_day: bool
    prev_trading_day: date
    next_trading_day: date


@router.get("/holidays", response_model=HolidayListResponse)
async def list_holidays(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> HolidayListResponse:
    q = select(NseHoliday).order_by(NseHoliday.holiday_date)
    if year is not None:
        q = q.where(
            NseHoliday.holiday_date >= date(year, 1, 1),
            NseHoliday.holiday_date <= date(year, 12, 31),
        )
    rows = (await db.execute(q)).scalars().all()
    return HolidayListResponse(
        total=len(rows),
        coverage_end=await market_calendar.coverage_end(db),
        holidays=[HolidayOut.model_validate(r) for r in rows],
    )


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
async def add_holiday(
    body: HolidayIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> HolidayOut:
    if body.holiday_date.weekday() > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Weekends are never stored — only weekday closures",
        )
    existing = await db.get(NseHoliday, body.holiday_date)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{body.holiday_date} already recorded: {existing.name}",
        )
    row = NseHoliday(holiday_date=body.holiday_date, name=body.name, source="manual")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return HolidayOut.model_validate(row)


@router.delete("/holidays/{holiday_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    row = await db.get(NseHoliday, holiday_date)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a recorded holiday")
    await db.delete(row)
    await db.commit()


@router.get("/special-sessions", response_model=list[SpecialSessionOut])
async def list_special_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[SpecialSessionOut]:
    rows = (await db.execute(
        select(NseSpecialSession).order_by(NseSpecialSession.session_date)
    )).scalars().all()
    return [SpecialSessionOut.model_validate(r) for r in rows]


@router.post("/special-sessions", response_model=SpecialSessionOut,
             status_code=status.HTTP_201_CREATED)
async def add_special_session(
    body: SpecialSessionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SpecialSessionOut:
    """Record a session NSE announced on a Saturday or Sunday, or a WEEKDAY session held at
    non-regular hours (a muhurat, which may fall on a holiday). A weekday row without hours
    would say nothing a weekday does not already say, so it is refused."""
    if body.session_date.weekday() <= 4 and body.open_ist is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A weekday is already a session — record one only with its non-regular hours",
        )
    if (body.open_ist is None) != (body.close_ist is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Give both open_ist and close_ist, or neither (regular hours)",
        )
    if body.open_ist is not None and body.close_ist is not None and body.open_ist >= body.close_ist:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="open_ist must be before close_ist",
        )
    existing = await db.get(NseSpecialSession, body.session_date)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{body.session_date} already recorded: {existing.name}",
        )
    row = NseSpecialSession(**body.model_dump(), source="manual")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return SpecialSessionOut.model_validate(row)


@router.delete("/special-sessions/{session_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_special_session(
    session_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    row = await db.get(NseSpecialSession, session_date)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Not a recorded special session")
    await db.delete(row)
    await db.commit()


class SessionNowOut(BaseModel):
    as_of: datetime
    today_ist: date
    is_trading_day: bool
    is_regular_session: bool
    open_ist: time | None
    close_ist: time | None
    in_session: bool
    next_open: datetime | None  # the next session's open (UTC), when not in session
    session_close: datetime | None  # today's close (UTC), when today is a session not yet closed


class ValidityOut(BaseModel):
    classification: str
    rule: str
    valid_until: datetime  # a signal created NOW, by the same path signal generation uses


class DataLimitOut(BaseModel):
    timeframe: str
    earliest: datetime | None
    latest: datetime | None


class ConstraintsOut(BaseModel):
    session: SessionNowOut
    validity: list[ValidityOut]
    offmarket_entry_allowed: bool
    offmarket_rule: str
    data_limits: list[DataLimitOut]


_VALIDITY_RULES = {
    "scalp": "30 minutes from creation",
    "intraday": "15:15 IST the same day (the next day once 15:15 has passed)",
    "swing": "5 trading days (NSE calendar)",
    "positional": "30 trading days (NSE calendar)",
}


def _now() -> datetime:
    """The clock seam — patched in tests so a weekday, a weekend and a holiday can be pinned."""
    return datetime.now(tz=UTC)


def _at_ist(d: date, t: time) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.combine(d, t, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC)


@router.get("/constraints", response_model=ConstraintsOut)
async def constraints(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    data_limits: bool = Query(
        default=True,
        description="include per-timeframe earliest/latest bars (a min/max scan per table) — "
        "the top-bar pill polls with false",
    ),
) -> ConstraintsOut:
    """A4 — the session and calendar constraints, queryable BEFORE a submit, the way
    `eligibility.py` made the gate answers queryable. Every answer comes from its owner (W2/W5):
    the calendar (sessions, incl. weekend specials), `compute_validity_until` (the path signal
    generation takes), the user's `allow_offmarket_entry`, and the candle tables themselves.
    It replaces guessing — the top-bar banner read OPEN on a weekday holiday."""
    from zoneinfo import ZoneInfo

    from sqlalchemy import text

    from app.broker.candle_aggregator import TIMEFRAME_TABLE
    from app.signals.expiry import compute_validity_until

    now = _now()
    today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    hours = await market_calendar.session_hours(db, today)
    in_session = await market_calendar.in_market_session(db, now)
    session_close = None
    next_open = None
    if hours is not None and now < _at_ist(today, hours[1]):
        session_close = _at_ist(today, hours[1])
        if now < _at_ist(today, hours[0]):
            next_open = _at_ist(today, hours[0])
    if next_open is None and not in_session:
        nxt = await market_calendar.next_trading_day(db, today)
        nxt_hours = await market_calendar.session_hours(db, nxt)
        if nxt_hours is not None:
            next_open = _at_ist(nxt, nxt_hours[0])

    validity = []
    for cls, rule in _VALIDITY_RULES.items():
        offset = await market_calendar.validity_offset_days(db, cls, now)
        validity.append(ValidityOut(classification=cls, rule=rule,
                                    valid_until=compute_validity_until(cls, now, offset)))

    tables = {**TIMEFRAME_TABLE, "1d": "ohlcv_1d"}  # the whitelist; names never come from input
    limits = []
    for tf, table in (tables.items() if data_limits else ()):
        row = (await db.execute(text(
            f"SELECT min(time), max(time) FROM {table}"  # noqa: S608 — whitelisted table
        ))).one()
        limits.append(DataLimitOut(timeframe=tf, earliest=row[0], latest=row[1]))

    return ConstraintsOut(
        session=SessionNowOut(
            as_of=now, today_ist=today, is_trading_day=hours is not None,
            is_regular_session=await market_calendar.is_regular_session(db, today),
            open_ist=hours[0] if hours else None, close_ist=hours[1] if hours else None,
            in_session=in_session, next_open=next_open, session_close=session_close,
        ),
        validity=validity,
        offmarket_entry_allowed=bool(user.allow_offmarket_entry),
        offmarket_rule=(
            "a paper order on a stock with no live price is refused unless off-market entry "
            "is allowed in your profile"
        ),
        data_limits=limits,
    )


@router.get("/trading-day", response_model=TradingDayOut)
async def trading_day_info(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    d: date | None = Query(default=None, description="Defaults to today (IST)"),
) -> TradingDayOut:
    from zoneinfo import ZoneInfo

    target = d or datetime.now(tz=ZoneInfo("Asia/Kolkata")).date()
    return TradingDayOut(
        for_date=target,
        is_trading_day=await market_calendar.is_trading_day(db, target),
        prev_trading_day=await market_calendar.prev_trading_day(db, target),
        next_trading_day=await market_calendar.next_trading_day(db, target),
    )
