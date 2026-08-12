"""Seasonality API schemas — monthly-return distribution (read-only)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MonthSeasonalityOut(BaseModel):
    month: int                       # 1..12
    n: int                           # yearly observations for this month
    positive: int
    pct_positive: float | None       # None when n == 0
    avg_return_pct: float | None
    median_return_pct: float | None
    best_return_pct: float | None
    worst_return_pct: float | None
    avg_positive_pct: float | None
    avg_negative_pct: float | None


class SeasonalityOut(BaseModel):
    stock_id: int
    total_observations: int          # total monthly returns counted
    years_covered: int               # distinct years contributing a return
    first_month: date | None
    last_month: date | None
    months: list[MonthSeasonalityOut]  # always 12, ordered month 1..12
