"""Market-calendar endpoints (Phase 2 slice 1).

GET  /calendar/holidays            — list holidays (optionally by year)
POST /calendar/holidays            — (admin) add a holiday (NSE circular)
DELETE /calendar/holidays/{date}   — (admin) remove a wrong entry
GET  /calendar/trading-day         — is a date a trading day (+ neighbours)
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.market_calendar import NseHoliday
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
