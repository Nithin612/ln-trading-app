"""Monthly-return seasonality endpoint — read-only context statistic.

  GET /seasonality/{stock_id}  — per-calendar-month return distribution built
                                 from the ingested daily OHLCV.

DISCOVERY / CONTEXT only: a seasonal bias is a soft modifier, never a signal
input — it never touches the confluence scorer. No look-ahead: completed months
strictly before the current IST month only (enforced in the service).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.seasonality import MonthSeasonalityOut, SeasonalityOut
from app.services import seasonality as sea
from app.services.stock_service import get_stock

router = APIRouter(prefix="/seasonality", tags=["seasonality"])


@router.get("/{stock_id}", response_model=SeasonalityOut)
async def get_seasonality(
    stock_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SeasonalityOut:
    stock = await get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    result = await sea.monthly_seasonality(db, stock_id)
    return SeasonalityOut(
        stock_id=result.stock_id,
        total_observations=result.total_observations,
        years_covered=result.years_covered,
        first_month=result.first_month,
        last_month=result.last_month,
        months=[
            MonthSeasonalityOut(
                month=mo.month,
                n=mo.n,
                positive=mo.positive,
                pct_positive=mo.pct_positive,
                avg_return_pct=mo.avg_return_pct,
                median_return_pct=mo.median_return_pct,
                best_return_pct=mo.best_return_pct,
                worst_return_pct=mo.worst_return_pct,
                avg_positive_pct=mo.avg_positive_pct,
                avg_negative_pct=mo.avg_negative_pct,
            )
            for mo in result.months
        ],
    )
