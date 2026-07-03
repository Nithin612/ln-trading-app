from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    CategoryWithCount,
    StockTagRead,
    StockTagRequest,
)
from app.schemas.stock import StockListResponse
from app.services.category_service import (
    create_category,
    delete_category,
    get_category,
    get_category_stocks,
    get_stock_categories,
    list_categories,
    tag_stock,
    untag_stock,
    update_category,
)

router = APIRouter(tags=["categories"])


# ── Category CRUD ─────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryWithCount])
async def list_categories_endpoint(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CategoryWithCount]:
    return await list_categories(db)


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_endpoint(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CategoryRead:
    cat = await create_category(db, payload, current_user.id)
    return CategoryRead.model_validate(cat)


@router.get("/categories/{category_id}", response_model=CategoryWithCount)
async def get_category_endpoint(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CategoryWithCount:
    return await get_category(db, category_id)


@router.put("/categories/{category_id}", response_model=CategoryRead)
async def update_category_endpoint(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> CategoryRead:
    cat = await update_category(db, category_id, payload)
    return CategoryRead.model_validate(cat)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    await delete_category(db, category_id)


@router.get("/categories/{category_id}/stocks", response_model=StockListResponse)
async def get_category_stocks_endpoint(
    category_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockListResponse:
    return await get_category_stocks(db, category_id, page, page_size)


# ── Stock tagging ─────────────────────────────────────────────────────────────

@router.get("/stocks/{stock_id}/categories", response_model=list[CategoryWithCount])
async def get_stock_categories_endpoint(
    stock_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CategoryWithCount]:
    return await get_stock_categories(db, stock_id)


@router.post(
    "/stocks/{stock_id}/categories",
    response_model=StockTagRead,
    status_code=status.HTTP_201_CREATED,
)
async def tag_stock_endpoint(
    stock_id: int,
    payload: StockTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> StockTagRead:
    tag = await tag_stock(db, stock_id, payload.category_id, current_user.id)
    return StockTagRead.model_validate(tag)


@router.delete(
    "/stocks/{stock_id}/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def untag_stock_endpoint(
    stock_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    await untag_stock(db, stock_id, category_id)
