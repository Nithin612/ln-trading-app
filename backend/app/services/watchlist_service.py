"""Watchlist CRUD — ownership is enforced HERE: every query scopes on
user_id, so a foreign watchlist id is indistinguishable from an absent
one (404, never 403 — don't leak existence)."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.stock import Stock
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemRead,
    WatchlistRead,
    WatchlistUpdate,
)


async def _owned_watchlist(
    db: AsyncSession, watchlist_id: int, user_id: int
) -> Watchlist:
    row = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id, Watchlist.user_id == user_id
        )
    )
    wl = row.scalar_one_or_none()
    if wl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found"
        )
    return wl


async def _read_model(db: AsyncSession, wl: Watchlist) -> WatchlistRead:
    rows = await db.execute(
        select(WatchlistItem, Stock.symbol, Stock.company_name)
        .join(Stock, Stock.id == WatchlistItem.stock_id)
        .where(WatchlistItem.watchlist_id == wl.id)
        .order_by(Stock.symbol)
    )
    items = [
        WatchlistItemRead(
            stock_id=item.stock_id,
            symbol=symbol,
            company_name=company_name,
            added_at=item.added_at,
        )
        for item, symbol, company_name in rows.all()
    ]
    return WatchlistRead(
        id=wl.id,
        name=wl.name,
        created_at=wl.created_at,
        updated_at=wl.updated_at,
        items=items,
    )


async def list_watchlists(db: AsyncSession, user_id: int) -> list[WatchlistRead]:
    rows = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.name)
    )
    return [await _read_model(db, wl) for wl in rows.scalars().all()]


async def create_watchlist(
    db: AsyncSession, payload: WatchlistCreate, user_id: int
) -> WatchlistRead:
    dup = await db.execute(
        select(Watchlist.id).where(
            Watchlist.user_id == user_id, Watchlist.name == payload.name
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Watchlist {payload.name!r} already exists",
        )
    wl = Watchlist(user_id=user_id, name=payload.name)
    db.add(wl)
    try:
        await db.commit()
    except IntegrityError:
        # Two concurrent creates race past the friendly pre-check; the
        # unique constraint backstops storage — surface the same 409,
        # never a 500 (bug-hunter LOW, 2026-07-11).
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Watchlist {payload.name!r} already exists",
        ) from None
    await db.refresh(wl)
    return await _read_model(db, wl)


async def rename_watchlist(
    db: AsyncSession, watchlist_id: int, payload: WatchlistUpdate, user_id: int
) -> WatchlistRead:
    wl = await _owned_watchlist(db, watchlist_id, user_id)
    dup = await db.execute(
        select(Watchlist.id).where(
            Watchlist.user_id == user_id,
            Watchlist.name == payload.name,
            Watchlist.id != watchlist_id,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Watchlist {payload.name!r} already exists",
        )
    wl.name = payload.name
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Watchlist {payload.name!r} already exists",
        ) from None
    await db.refresh(wl)
    return await _read_model(db, wl)


async def delete_watchlist(
    db: AsyncSession, watchlist_id: int, user_id: int
) -> None:
    wl = await _owned_watchlist(db, watchlist_id, user_id)
    await db.delete(wl)
    await db.commit()


async def add_stock(
    db: AsyncSession, watchlist_id: int, stock_id: int, user_id: int
) -> WatchlistRead:
    wl = await _owned_watchlist(db, watchlist_id, user_id)
    stock = await db.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
        )
    existing = await db.get(WatchlistItem, (watchlist_id, stock_id))
    if existing is None:  # idempotent add — re-adding is not an error
        db.add(WatchlistItem(watchlist_id=watchlist_id, stock_id=stock_id))
        await db.commit()
    return await _read_model(db, wl)


async def remove_stock(
    db: AsyncSession, watchlist_id: int, stock_id: int, user_id: int
) -> WatchlistRead:
    wl = await _owned_watchlist(db, watchlist_id, user_id)
    item = await db.get(WatchlistItem, (watchlist_id, stock_id))
    if item is not None:  # idempotent remove
        await db.delete(item)
        await db.commit()
    return await _read_model(db, wl)


async def watchlist_stock_ids(
    db: AsyncSession, watchlist_id: int, user_id: int
) -> set[int] | None:
    """stock_ids of the user's watchlist, or None when it isn't theirs /
    doesn't exist. None ≠ empty set: an empty watchlist legitimately
    scopes to NOTHING, while None means the caller must reject."""
    owned = await db.execute(
        select(Watchlist.id).where(
            Watchlist.id == watchlist_id, Watchlist.user_id == user_id
        )
    )
    if owned.scalar_one_or_none() is None:
        return None
    rows = await db.execute(
        select(WatchlistItem.stock_id).where(
            WatchlistItem.watchlist_id == watchlist_id
        )
    )
    return {sid for (sid,) in rows.all()}
