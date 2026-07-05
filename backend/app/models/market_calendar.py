"""NSE market-calendar model — trading holidays (Phase 2 slice 1).

Trading-day arithmetic (SIGNAL_ENGINE.md §5 validity, task scheduling)
must use this table, never calendar-day approximations
(.claude/rules/trading-domain.md).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, func
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
