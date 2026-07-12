from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.watchlist import (
    StockRef,
    WatchlistCreate,
    WatchlistRead,
    WatchlistUpdate,
)
from app.services.watchlist_service import (
    add_stock,
    create_watchlist,
    delete_watchlist,
    list_watchlists,
    remove_stock,
    rename_watchlist,
)

router = APIRouter(tags=["watchlists"])


@router.get("/watchlists", response_model=list[WatchlistRead])
async def list_watchlists_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WatchlistRead]:
    return await list_watchlists(db, current_user.id)


@router.post(
    "/watchlists", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED
)
async def create_watchlist_endpoint(
    payload: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    return await create_watchlist(db, payload, current_user.id)


@router.patch("/watchlists/{watchlist_id}", response_model=WatchlistRead)
async def rename_watchlist_endpoint(
    watchlist_id: Annotated[int, Path(gt=0, lt=2**63)],
    payload: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    return await rename_watchlist(db, watchlist_id, payload, current_user.id)


@router.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_endpoint(
    watchlist_id: Annotated[int, Path(gt=0, lt=2**63)],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await delete_watchlist(db, watchlist_id, current_user.id)


@router.post("/watchlists/{watchlist_id}/stocks", response_model=WatchlistRead)
async def add_stock_endpoint(
    watchlist_id: Annotated[int, Path(gt=0, lt=2**63)],
    payload: StockRef,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    return await add_stock(db, watchlist_id, payload.stock_id, current_user.id)


@router.delete(
    "/watchlists/{watchlist_id}/stocks/{stock_id}", response_model=WatchlistRead
)
async def remove_stock_endpoint(
    watchlist_id: Annotated[int, Path(gt=0, lt=2**63)],
    stock_id: Annotated[int, Path(gt=0, lt=2**63)],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    return await remove_stock(db, watchlist_id, stock_id, current_user.id)
