"""NSE market-calendar model — trading holidays (Phase 2 slice 1).

Trading-day arithmetic (SIGNAL_ENGINE.md §5 validity, task scheduling)
must use this table, never calendar-day approximations
(.claude/rules/trading-domain.md).
"""

from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)


class NseHoliday(Base):
    """One NSE cash-market trading holiday (weekday market closures only —
    weekends are handled arithmetically and never stored here)."""

    __tablename__ = "nse_holidays"

    holiday_date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # provenance: "derived" (from bhavcopy session gaps — ground truth for
    # the past) · "published" (NSE circular) · "manual" (admin entry)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )


class NseSpecialSession(Base):
    """One exchange session held on a day the weekday rule calls closed — a Saturday or Sunday
    (Union Budget days, DR drills, muhurat trading). Without this table the calendar cannot
    represent them: `is_trading_day` returned False for every weekend, so EOD ingest, the
    catch-up healer and every scheduled task were blind to sessions that really happened
    (8 in the archive: 2019-10-27 … 2026-02-01).

    `open_ist` / `close_ist` are the session's hours when they differ from 09:15–15:30 (a
    muhurat session is ~1 hour in the evening); NULL means "regular hours or not recorded".
    ⚠ ONE window: a split session (a DR drill's 09:15–10:00 + 11:30–12:30) cannot be described,
    so record its envelope and accept that the gap reads as open. A row with any hours is
    "not a regular session", which already keeps the CAS capture, intraday profiles and nightly
    generation off it."""

    __tablename__ = "nse_special_sessions"

    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    open_ist: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_ist: Mapped[time | None] = mapped_column(Time, nullable=True)
    # provenance: "derived" (a bhavcopy exists for the date — ground truth for the past) ·
    # "published" (NSE circular) · "manual" (admin entry)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )
