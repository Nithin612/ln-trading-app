"""
Screener request → SQLAlchemy Select compiler.

Security model: every field name and operator is validated against the catalog
whitelist before any SQL is produced.  Unknown fields raise ValueError — never
a DB error.  Value coercion is explicit per field_type.
"""
from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, asc, desc, func, or_, select

from app.models.category import StockCategory
from app.models.stock import Stock
from app.schemas.screener import FilterSpec, ScreenerRequest
from app.screener.catalog import CATALOG, SORT_FIELDS

# ---------------------------------------------------------------------------
# Value coercion helpers
# ---------------------------------------------------------------------------

def _coerce(value: Any, field_type: str) -> Any:
    """Cast a raw JSON value to the Python type expected by the column."""
    try:
        if field_type == "bool":
            if isinstance(value, bool):
                return value
            raise ValueError
        if field_type == "int":
            return int(value)
        if field_type == "decimal":
            return Decimal(str(value))
        if field_type == "date":
            return datetime.date.fromisoformat(str(value))
        # str
        return str(value)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot coerce value {value!r} to type {field_type}",
        ) from exc


def _coerce_list(values: Any, field_type: str) -> list[Any]:
    if not isinstance(values, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'in' and 'between' operators require a list value",
        )
    return [_coerce(v, field_type) for v in values]


# ---------------------------------------------------------------------------
# Clause builder for a single FilterSpec
# ---------------------------------------------------------------------------

def _build_clause(spec: FilterSpec) -> Any:  # noqa: C901
    field_name = spec.field
    op = spec.op

    if field_name not in CATALOG:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown screener field: {field_name!r}",
        )

    field_def = CATALOG[field_name]

    if not field_def.available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Field {field_name!r} is not yet available. "
                f"{field_def.note}"
            ),
        )

    if op not in field_def.allowed_ops:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Operator {op!r} is not allowed for field {field_name!r}. "
                f"Allowed: {sorted(field_def.allowed_ops)}"
            ),
        )

    col = field_def.column
    ft = field_def.field_type

    if op == "eq":
        return col == _coerce(spec.value, ft)
    if op == "neq":
        return col != _coerce(spec.value, ft)
    if op == "gt":
        return col > _coerce(spec.value, ft)
    if op == "gte":
        return col >= _coerce(spec.value, ft)
    if op == "lt":
        return col < _coerce(spec.value, ft)
    if op == "lte":
        return col <= _coerce(spec.value, ft)
    if op == "like":
        return col.ilike(f"%{_coerce(spec.value, ft)}%")
    if op == "in":
        values = _coerce_list(spec.value, ft)
        return col.in_(values)
    if op == "between":
        bounds = _coerce_list(spec.value, ft)
        if len(bounds) != 2:  # noqa: PLR2004
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="'between' requires exactly 2 values: [low, high]",
            )
        return col.between(bounds[0], bounds[1])


# ---------------------------------------------------------------------------
# Full query compiler
# ---------------------------------------------------------------------------

def _apply_category_filter(stmt: Any, category_ids: list[int]) -> Any:
    """Restrict to stocks tagged with ALL given categories (AND semantics)."""
    for cat_id in category_ids:
        exists_sub = (
            select(StockCategory.stock_id)
            .where(
                StockCategory.stock_id == Stock.id,
                StockCategory.category_id == cat_id,
            )
            .exists()
        )
        stmt = stmt.where(exists_sub)
    return stmt


def compile_screener(req: ScreenerRequest) -> Select[tuple[Stock]]:
    """Return a SQLAlchemy Select that can be executed on an async session."""
    stmt = select(Stock).where(Stock.is_active == True)  # noqa: E712

    if req.filters:
        clauses = [_build_clause(f) for f in req.filters]
        stmt = stmt.where(and_(*clauses) if req.logic == "AND" else or_(*clauses))

    if req.category_ids:
        stmt = _apply_category_filter(stmt, req.category_ids)

    sort_col = SORT_FIELDS.get(req.sort_by)
    if sort_col is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown sort field: {req.sort_by!r}",
        )
    stmt = stmt.order_by(asc(sort_col) if req.sort_dir == "asc" else desc(sort_col))

    return stmt


def compile_count(req: ScreenerRequest) -> Select[tuple[int]]:
    """Count query matching compile_screener (without ORDER BY / limit / offset)."""
    # Build a subquery identical to compile_screener but selecting only Stock.id,
    # then wrap it with COUNT(*). This keeps the logic in one place.
    inner = select(Stock.id).where(Stock.is_active == True)  # noqa: E712

    if req.filters:
        clauses = [_build_clause(f) for f in req.filters]
        inner = inner.where(and_(*clauses) if req.logic == "AND" else or_(*clauses))

    if req.category_ids:
        inner = _apply_category_filter(inner, req.category_ids)

    return select(func.count()).select_from(inner.subquery())
