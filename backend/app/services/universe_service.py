"""Universe resolution — which stocks a profile / backtest runs over
(Phase 2 slice 4; lifted from api/v1/strategy.py so the suggestions
pipeline and walk-forward runner don't import an API module).
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, StockCategory
from app.models.stock import Stock
from app.schemas.profile import UniverseSpec


async def resolve_universe(
    db: AsyncSession, spec: UniverseSpec | dict[str, Any]
) -> tuple[list[int], dict[int, str]]:
    """Return (stock_ids, {id: symbol}) for a typed universe spec.

    Only is_active stocks ever resolve. Unknown kinds are rejected by the
    UniverseSpec discriminator (reject-don't-clamp).
    """
    from pydantic import TypeAdapter

    parsed = (
        spec
        if not isinstance(spec, dict)
        else TypeAdapter(UniverseSpec).validate_python(spec)
    )

    base = select(Stock.id, Stock.symbol).where(Stock.is_active.is_(True))
    if parsed.kind == "index":
        col = Stock.is_nifty50 if parsed.value == "NIFTY50" else Stock.is_banknifty
        q = base.where(col.is_(True))
    elif parsed.kind == "flag":
        q = base.where(Stock.is_fno.is_(True))
    elif parsed.kind == "symbols":
        q = base.where(Stock.symbol.in_(parsed.value))
    elif parsed.kind == "category":
        q = (
            base.join(StockCategory, StockCategory.stock_id == Stock.id)
            .join(Category, Category.id == StockCategory.category_id)
            .where(Category.slug == parsed.value)
        )
    else:  # all_active
        q = base

    rows = (await db.execute(q)).fetchall()
    return [r[0] for r in rows], {r[0]: r[1] for r in rows}


async def resolve_legacy(
    db: AsyncSession, universe: str, symbols: list[str] | None
) -> tuple[list[int], dict[int, str]]:
    """The v1 strategy-lab resolver semantics, expressed over resolve_universe."""
    if symbols:
        return await resolve_universe(db, {"kind": "symbols", "value": symbols})
    u = universe.upper()
    if u in ("NIFTY50", "BANKNIFTY"):
        return await resolve_universe(db, {"kind": "index", "value": u})
    if u == "FNO":
        return await resolve_universe(db, {"kind": "flag", "value": "fno"})
    return await resolve_universe(db, {"kind": "all_active"})
