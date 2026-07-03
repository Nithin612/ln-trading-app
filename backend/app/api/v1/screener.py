from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.stock import SavedScreen, Stock
from app.models.user import User
from app.schemas.screener import (
    SavedScreenCreate,
    SavedScreenRead,
    ScreenerRequest,
    ScreenerResult,
)
from app.schemas.stock import StockRead
from app.screener.compiler import compile_count, compile_screener

router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("/run", response_model=ScreenerResult)
async def run_screener(
    req: ScreenerRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScreenerResult:
    count_stmt = compile_count(req)
    total: int = (await db.execute(count_stmt)).scalar_one()

    query_stmt = compile_screener(req).offset(req.offset).limit(req.limit)
    rows: list[Stock] = list((await db.execute(query_stmt)).scalars().all())

    return ScreenerResult(
        items=[StockRead.model_validate(r) for r in rows],
        total=total,
        limit=req.limit,
        offset=req.offset,
    )


@router.get("/saved", response_model=list[SavedScreenRead])
async def list_saved_screens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SavedScreen]:
    result = await db.execute(
        select(SavedScreen)
        .where(SavedScreen.user_id == current_user.id)
        .order_by(SavedScreen.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post("/saved", response_model=SavedScreenRead, status_code=status.HTTP_201_CREATED)
async def create_saved_screen(
    payload: SavedScreenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedScreen:
    # Enforce uniqueness per user — surface a clear error rather than a DB exception
    existing = await db.execute(
        select(SavedScreen).where(
            SavedScreen.user_id == current_user.id,
            SavedScreen.name == payload.name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A saved screen named {payload.name!r} already exists.",
        )

    screen = SavedScreen(
        user_id=current_user.id,
        name=payload.name,
        filter_spec=payload.filter_spec.model_dump(),
    )
    db.add(screen)
    await db.commit()
    await db.refresh(screen)
    return screen


@router.delete(
    "/saved/{screen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_saved_screen(
    screen_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(SavedScreen).where(
            SavedScreen.id == screen_id,
            SavedScreen.user_id == current_user.id,
        )
    )
    screen = result.scalar_one_or_none()
    if screen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved screen not found")
    await db.delete(screen)
    await db.commit()
