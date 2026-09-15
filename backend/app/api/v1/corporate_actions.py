"""Corporate-action endpoints — Phase 6.8.5 (admin).

POST /corporate-actions  — (admin) record a VERIFIED split/bonus (ratio + ex-date)
GET  /corporate-actions  — (admin) list recent/upcoming corporate actions
GET  /corporate-actions/quarantine                   — (admin) the CA review queue
GET  /corporate-actions/quarantine/{id}/history      — (admin) append-only flag log
POST /corporate-actions/quarantine/{id}/clear        — (admin) release, with a reason

The ratio is entered/verified by a human — never guessed from a price gap or
parsed from headline text. The ex-date worker (`corporate_action_tasks`) then
R-preservingly adjusts open paper positions on the ex-date. There is no
auto-population from a feed yet (deferred: needs a structured NSE CA source).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models.corporate_action import CaFlagEvent, CorporateAction
from app.models.stock import Stock
from app.models.user import User
from app.schemas.corporate_action import (
    CaClearRequest,
    CaFlagEventOut,
    CaQuarantineOut,
    CorporateActionCreate,
    CorporateActionOut,
)
from app.services.ca_adjust import record_corporate_action
from app.services.ca_quarantine import (
    FlaggedStock,
    NotFlaggedError,
    clear_flag,
    history,
    list_flagged,
)

router = APIRouter(prefix="/corporate-actions", tags=["corporate-actions"])


@router.post(
    "",
    response_model=CorporateActionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_corporate_action(
    req: CorporateActionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CorporateAction:
    """Record a verified corporate action. 404 if the stock is unknown, 409 if an
    action for the same (stock, ex-date, type) already exists, 422 on a bad ratio."""
    if await db.get(Stock, req.stock_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    try:
        ca = await record_corporate_action(
            db,
            stock_id=req.stock_id,
            action_type=req.action_type,
            ex_date=req.ex_date,
            ratio_from=req.ratio_from,
            ratio_to=req.ratio_to,
            note=req.note,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A corporate action for this stock, ex-date and type already exists",
        ) from exc
    await db.refresh(ca)
    return ca


@router.get(
    "",
    response_model=list[CorporateActionOut],
    dependencies=[Depends(require_admin)],
)
async def list_corporate_actions(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CorporateAction]:
    """Recent/upcoming corporate actions, newest ex-date first."""
    rows = (
        await db.execute(
            select(CorporateAction).order_by(CorporateAction.ex_date.desc()).limit(limit)
        )
    ).scalars().all()
    return list(rows)


@router.get(
    "/quarantine",
    response_model=list[CaQuarantineOut],
    dependencies=[Depends(require_admin)],
)
async def list_quarantine(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FlaggedStock]:
    """The CA review queue — every stock the detector is holding out of suggestion
    universes, oldest first.

    ⚠ Includes INACTIVE names: the quarantine and the universe rule are independent, and
    a reviewer should see the whole set rather than today's tradeable subset."""
    return await list_flagged(db)


@router.get(
    "/quarantine/{stock_id}/history",
    response_model=list[CaFlagEventOut],
    dependencies=[Depends(require_admin)],
)
async def quarantine_history(
    stock_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CaFlagEvent]:
    """Every flag and clear for one stock, oldest first. Append-only: a later flag never
    erases the review that released the previous one."""
    return await history(db, stock_id=stock_id)


@router.post(
    "/quarantine/{stock_id}/clear",
    response_model=CaQuarantineOut,
    dependencies=[Depends(require_admin)],
)
async def clear_quarantine(
    stock_id: int,
    req: CaClearRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> FlaggedStock:
    """Release a stock from CA quarantine, recording who and why. 404 when it is not
    currently quarantined.

    ⭐ This is the path `ca_detector`'s docstring promised ("unflag via admin after
    verifying") and that did not exist: the flag had one writer and no clearer anywhere,
    so the quarantine only ever grew — 7 names by 2026-09-14, 4 of them added that day.

    ⚠ Clearing asserts the unadjusted history is SAFE TO SCORE again — because the gap
    was a real price move, because the series has since been adjusted, or because the bad
    bars have aged out of every indicator window. It adjusts nothing. If the name
    genuinely needs adjusting, use `POST /corporate-actions` with a verified ratio.
    """
    try:
        return await clear_flag(
            db, stock_id=stock_id, actor_user_id=admin.id, reason=req.reason
        )
    except NotFlaggedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
