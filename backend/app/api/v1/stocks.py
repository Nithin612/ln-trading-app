from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.stock import Stock
from app.models.user import User
from app.schemas.stock import (
    ResolvedStockOut,
    StockListParams,
    StockListResponse,
    StockRead,
    StockSearchResponse,
)
from app.services.stock_resolve import resolve_former_symbol, resolve_search
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


@router.get("/search", response_model=StockSearchResponse)
async def search_stocks_endpoint(
    q: str = Query(..., min_length=1, description="Symbol or company name, current or former"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockSearchResponse:
    """V4 / A2 — search that answers ABSENCE.

    ⭐ Everywhere else a name the universe rule excluded simply is not there, and the user
    cannot ask why (§45/S2: *an absence is not askable*). Search is the one surface where
    they name a specific stock, so it is the one place the question can be answered.

    ⚠ **Deliberately does NOT filter by `is_active`.** The list endpoint defaults it to
    True, which is why 1,104 of 3,395 stocks — measured — return nothing today, with no
    distinction between "no such company" and "excluded, and here is why". Excluded names
    are returned, ranked BELOW usable ones, carrying their reason.

    ⚠ Declared before `/{stock_id}`: FastAPI matches in order, and a literal path
    registered after a parameterised one is shadowed by it.
    """
    params = StockListParams(q=q, is_active=None, page=1, page_size=limit)
    listing = await list_stocks(db, params)
    ids = [row.id for row in listing.items]
    stocks = list(
        (await db.execute(select(Stock).where(Stock.id.in_(ids)))).scalars()
    ) if ids else []

    resolution = await resolve_search(db, q, stocks=stocks)

    # A7 — the query may name a ticker the market no longer uses. A rename keeps the row
    # id, so the company is still here under a different name; without this the user gets
    # a dead end for a stock they own.
    if not resolution.hits:
        former = await resolve_former_symbol(db, q)
        if former is not None:
            resolution = await resolve_search(db, q, stocks=[former])
            resolution.matched_former_symbol = q.strip().upper()

    return StockSearchResponse(
        query=resolution.query,
        hits=[
            ResolvedStockOut(
                stock_id=h.stock_id,
                symbol=h.symbol,
                company_name=h.company_name,
                in_universe=h.in_universe,
                ca_quarantined=h.ca_quarantined,
                suggestible=h.suggestible,
                exclusion_reasons=list(h.exclusion_reasons),
                former_symbols=list(h.former_symbols),
                reason_as_of=h.reason_as_of,
            )
            for h in resolution.hits
        ],
        matched_former_symbol=resolution.matched_former_symbol,
    )


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
