"""
Stock service — CRUD and paginated list with optional relevance-ranked search.

Search matches on a substring (ILIKE) of symbol OR company name, so typing
"tata" reliably finds every TATA* symbol, plus Postgres pg_trgm similarity (%)
for typo tolerance. Results are RANKED by match quality — exact symbol, then
symbol prefix, name prefix, symbol substring, name substring, then trigram-only
— so the intended stock surfaces first regardless of the table sort (previously
matches were ordered by market cap, which is NULL for most rows, burying exact
matches). The trigram threshold is 0.3: substring hits already cover the obvious
matches, so the looser 0.1 only added noise (typing "tata" dredged up TRENT/ATAM).
"""
from __future__ import annotations

import math

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.schemas.stock import StockListParams, StockListResponse, StockRead
from app.screener.catalog import SORT_FIELDS

_TRGM_THRESHOLD = 0.3


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

    # ── Relevance-ranked search ───────────────────────────────────────────────
    relevance = None
    if params.q and params.q.strip():
        # SET doesn't accept bind parameters in asyncpg; the threshold is a
        # hardcoded constant so f-string interpolation is safe here.
        await db.execute(text(f"SET pg_trgm.similarity_threshold = {_TRGM_THRESHOLD}"))
        raw = params.q.strip()
        up = raw.upper()
        like = f"%{up}%"
        prefix = f"{up}%"
        # Substring (ILIKE) guarantees every symbol/name CONTAINING the query
        # is matched; the trigram operator (%) adds typo tolerance on top.
        search_clause = or_(
            Stock.symbol.ilike(like),
            Stock.company_name.ilike(like),
            Stock.symbol.op("%")(up),
            Stock.company_name.op("%")(raw),
        )
        stmt = stmt.where(search_clause)
        count_stmt = count_stmt.where(search_clause)
        # Rank best matches first (lower = better). The table sort becomes the
        # tiebreak WITHIN a tier, so an exact/prefix hit is never buried.
        relevance = case(
            (Stock.symbol == up, 0),
            (Stock.symbol.ilike(prefix), 1),
            (Stock.company_name.ilike(prefix), 2),
            (Stock.symbol.ilike(like), 3),
            (Stock.company_name.ilike(like), 4),
            else_=5,
        )

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
    primary = sort_col.asc() if params.sort_dir == "asc" else sort_col.desc()
    # Relevance dominates when searching; symbol is a stable final tiebreak so
    # pagination is deterministic even when the sort column has ties/NULLs.
    if relevance is not None:
        stmt = stmt.order_by(relevance.asc(), primary, Stock.symbol.asc())
    else:
        stmt = stmt.order_by(primary, Stock.symbol.asc())

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
