"""
Stock service — CRUD and paginated list with optional fuzzy search.

Fuzzy search uses Postgres's pg_trgm similarity operator (%) so that typing
"tata" matches "TATAMOTORS" and "Tata Consultancy Services Ltd." together.
The similarity threshold is 0.1 (permissive for short queries).
"""
from __future__ import annotations

import math

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.schemas.stock import StockListParams, StockListResponse, StockRead
from app.screener.catalog import SORT_FIELDS

_TRGM_THRESHOLD = 0.1


async def get_stock(db: AsyncSession, stock_id: int) -> Stock | None:
    result = await db.execute(select(Stock).where(Stock.id == stock_id))
    return result.scalar_one_or_none()


async def get_stock_by_symbol(
    db: AsyncSession, symbol: str, exchange: str = "NSE"
) -> Stock | None:
    result = await db.execute(
        select(Stock).where(Stock.symbol == symbol, Stock.exchange == exchange)
    )
    return result.scalar_one_or_none()


async def list_stocks(db: AsyncSession, params: StockListParams) -> StockListResponse:
    stmt = select(Stock)
    count_stmt = select(func.count()).select_from(Stock)

    # ── Fuzzy search ──────────────────────────────────────────────────────────
    if params.q:
        # Set similarity threshold for this session query
        # SET doesn't accept bind parameters in asyncpg; the threshold is a
        # hardcoded constant so f-string interpolation is safe here.
        await db.execute(text(f"SET pg_trgm.similarity_threshold = {_TRGM_THRESHOLD}"))
        q = params.q.upper()
        search_clause = or_(
            Stock.symbol.op("%")(q),
            Stock.company_name.op("%")(params.q),
        )
        stmt = stmt.where(search_clause)
        count_stmt = count_stmt.where(search_clause)

    # ── Boolean / categorical filters ─────────────────────────────────────────
    if params.is_active is not None:
        stmt = stmt.where(Stock.is_active == params.is_active)
        count_stmt = count_stmt.where(Stock.is_active == params.is_active)
    if params.sector is not None:
        stmt = stmt.where(Stock.sector == params.sector)
        count_stmt = count_stmt.where(Stock.sector == params.sector)
    if params.is_nifty50 is not None:
        stmt = stmt.where(Stock.is_nifty50 == params.is_nifty50)
        count_stmt = count_stmt.where(Stock.is_nifty50 == params.is_nifty50)
    if params.is_banknifty is not None:
        stmt = stmt.where(Stock.is_banknifty == params.is_banknifty)
        count_stmt = count_stmt.where(Stock.is_banknifty == params.is_banknifty)
    if params.is_finnifty is not None:
        stmt = stmt.where(Stock.is_finnifty == params.is_finnifty)
        count_stmt = count_stmt.where(Stock.is_finnifty == params.is_finnifty)
    if params.is_fno is not None:
        stmt = stmt.where(Stock.is_fno == params.is_fno)
        count_stmt = count_stmt.where(Stock.is_fno == params.is_fno)

    # ── Sort ──────────────────────────────────────────────────────────────────
    sort_col = SORT_FIELDS.get(params.sort_by, Stock.symbol)
    stmt = stmt.order_by(
        sort_col.asc() if params.sort_dir == "asc" else sort_col.desc()
    )

    # ── Count (before pagination) ─────────────────────────────────────────────
    total: int = (await db.execute(count_stmt)).scalar_one()

    # ── Pagination ────────────────────────────────────────────────────────────
    offset = (params.page - 1) * params.page_size
    stmt = stmt.offset(offset).limit(params.page_size)

    rows = (await db.execute(stmt)).scalars().all()

    return StockListResponse(
        items=[StockRead.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=max(1, math.ceil(total / params.page_size)),
    )
