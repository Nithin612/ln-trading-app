from __future__ import annotations

import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, StockCategory, _slugify
from app.models.stock import Stock
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryWithCount
from app.schemas.stock import StockListResponse, StockRead


async def _assert_stock_exists(db: AsyncSession, stock_id: int) -> None:
    row = await db.execute(select(Stock.id).where(Stock.id == stock_id))
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")


async def _assert_category_exists(db: AsyncSession, category_id: int) -> Category:
    row = await db.execute(select(Category).where(Category.id == category_id))
    cat = row.scalar_one_or_none()
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )
    return cat


async def create_category(
    db: AsyncSession,
    payload: CategoryCreate,
    user_id: int,
) -> Category:
    slug = _slugify(payload.name)

    existing = await db.execute(select(Category).where(Category.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category {payload.name!r} already exists",
        )

    slug_exists = await db.execute(select(Category).where(Category.slug == slug))
    if slug_exists.scalar_one_or_none() is not None:
        # Append id-like suffix to guarantee uniqueness
        count = await db.execute(select(func.count()).select_from(Category))
        slug = f"{slug}-{count.scalar_one() + 1}"

    cat = Category(
        name=payload.name,
        slug=slug,
        description=payload.description,
        created_by=user_id,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def list_categories(db: AsyncSession) -> list[CategoryWithCount]:
    # Fetch categories with a stock_count via correlated subquery
    stock_count_sq = (
        select(func.count())
        .select_from(StockCategory)
        .where(StockCategory.category_id == Category.id)
        .scalar_subquery()
    )
    stmt = select(Category, stock_count_sq.label("stock_count")).order_by(Category.name)
    rows = (await db.execute(stmt)).all()

    result: list[CategoryWithCount] = []
    for cat, count in rows:
        data = CategoryWithCount.model_validate(cat)
        data.stock_count = count
        result.append(data)
    return result


async def get_category(db: AsyncSession, category_id: int) -> CategoryWithCount:
    cat = await _assert_category_exists(db, category_id)
    count_row = await db.execute(
        select(func.count())
        .select_from(StockCategory)
        .where(StockCategory.category_id == category_id)
    )
    result = CategoryWithCount.model_validate(cat)
    result.stock_count = count_row.scalar_one()
    return result


async def update_category(
    db: AsyncSession,
    category_id: int,
    payload: CategoryUpdate,
) -> Category:
    cat = await _assert_category_exists(db, category_id)

    if payload.name is not None and payload.name != cat.name:
        existing = await db.execute(
            select(Category).where(Category.name == payload.name)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category {payload.name!r} already exists",
            )
        cat.name = payload.name
        cat.slug = _slugify(payload.name)

    if payload.description is not None:
        cat.description = payload.description

    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, category_id: int) -> None:
    cat = await _assert_category_exists(db, category_id)
    await db.delete(cat)
    await db.commit()


async def tag_stock(
    db: AsyncSession,
    stock_id: int,
    category_id: int,
    user_id: int,
) -> StockCategory:
    await _assert_stock_exists(db, stock_id)
    await _assert_category_exists(db, category_id)

    existing = await db.execute(
        select(StockCategory).where(
            StockCategory.stock_id == stock_id,
            StockCategory.category_id == category_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock is already tagged with this category",
        )

    tag = StockCategory(stock_id=stock_id, category_id=category_id, tagged_by=user_id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def untag_stock(
    db: AsyncSession,
    stock_id: int,
    category_id: int,
) -> None:
    row = await db.execute(
        select(StockCategory).where(
            StockCategory.stock_id == stock_id,
            StockCategory.category_id == category_id,
        )
    )
    tag = row.scalar_one_or_none()
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag association not found",
        )
    await db.delete(tag)
    await db.commit()


async def get_stock_categories(
    db: AsyncSession,
    stock_id: int,
) -> list[CategoryWithCount]:
    await _assert_stock_exists(db, stock_id)
    stmt = (
        select(Category)
        .join(StockCategory, StockCategory.category_id == Category.id)
        .where(StockCategory.stock_id == stock_id)
        .order_by(Category.name)
    )
    cats = list((await db.execute(stmt)).scalars().all())

    result: list[CategoryWithCount] = []
    for cat in cats:
        count_row = await db.execute(
            select(func.count())
            .select_from(StockCategory)
            .where(StockCategory.category_id == cat.id)
        )
        data = CategoryWithCount.model_validate(cat)
        data.stock_count = count_row.scalar_one()
        result.append(data)
    return result


async def get_category_stocks(
    db: AsyncSession,
    category_id: int,
    page: int = 1,
    page_size: int = 50,
) -> StockListResponse:
    await _assert_category_exists(db, category_id)

    base = (
        select(Stock)
        .join(StockCategory, StockCategory.stock_id == Stock.id)
        .where(StockCategory.category_id == category_id, Stock.is_active == True)  # noqa: E712
    )
    count_stmt = (
        select(func.count())
        .select_from(Stock)
        .join(StockCategory, StockCategory.stock_id == Stock.id)
        .where(StockCategory.category_id == category_id, Stock.is_active == True)  # noqa: E712
    )

    total: int = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * page_size
    rows = list(
        (await db.execute(base.order_by(Stock.symbol).offset(offset).limit(page_size)))
        .scalars()
        .all()
    )

    return StockListResponse(
        items=[StockRead.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )
