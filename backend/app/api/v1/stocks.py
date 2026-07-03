from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.stock import StockListParams, StockListResponse, StockRead
from app.services.stock_service import get_stock, list_stocks

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
async def list_stocks_endpoint(
    q: str | None = Query(None, description="Fuzzy search on symbol or company name"),
    sector: str | None = Query(None),
    is_nifty50: bool | None = Query(None),
    is_banknifty: bool | None = Query(None),
    is_finnifty: bool | None = Query(None),
    is_fno: bool | None = Query(None),
    is_active: bool | None = Query(True),
    sort_by: str = Query("symbol"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockListResponse:
    params = StockListParams(
        q=q,
        sector=sector,
        is_nifty50=is_nifty50,
        is_banknifty=is_banknifty,
        is_finnifty=is_finnifty,
        is_fno=is_fno,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return await list_stocks(db, params)


@router.get("/{stock_id}", response_model=StockRead)
async def get_stock_endpoint(
    stock_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockRead:
    stock = await get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return StockRead.model_validate(stock)
