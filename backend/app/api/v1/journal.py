"""Trading journal endpoints — Phase 10.

GET  /journal/                        — list entries (search, filters, pagination)
POST /journal/                        — create manual entry
GET  /journal/analytics/emotions      — emotion distribution analytics
GET  /journal/{id}                    — get single entry
PUT  /journal/{id}                    — update entry
DELETE /journal/{id}                  — delete entry
POST /journal/{id}/screenshots        — upload screenshot (multipart)
DELETE /journal/{id}/screenshots/{fn} — remove screenshot
"""

import mimetypes
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.journal import JournalEntry
from app.models.stock import Stock
from app.models.user import User
from app.schemas.journal import (
    EmotionAnalyticsOut,
    EmotionCount,
    JournalEntryCreate,
    JournalEntryOut,
    JournalEntryUpdate,
    JournalListResponse,
)

router = APIRouter(prefix="/journal", tags=["journal"])

_IST = ZoneInfo("Asia/Kolkata")
_ALLOWED_IMAGE_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)


def _uploads_dir(user_id: int, entry_id: str) -> Path:
    p = Path(settings.uploads_dir) / "screenshots" / str(user_id) / entry_id
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _symbol(db: AsyncSession, stock_id: int | None) -> str | None:
    if stock_id is None:
        return None
    s = await db.get(Stock, stock_id)
    return s.symbol if s else None


def _enrich(entry: JournalEntry, sym: str | None) -> JournalEntryOut:
    out = JournalEntryOut.model_validate(entry)
    out.symbol = sym
    return out


@router.get("/analytics/emotions", response_model=EmotionAnalyticsOut)
async def emotion_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> EmotionAnalyticsOut:
    """Return emotion distribution and average P&L grouped by emotion_before and emotion_after."""
    total_result = await db.execute(
        select(func.count(JournalEntry.id)).where(JournalEntry.user_id == user.id)
    )
    total = int(total_result.scalar() or 0)

    before_result = await db.execute(
        select(
            JournalEntry.emotion_before,
            func.count(JournalEntry.id).label("cnt"),
            func.avg(JournalEntry.realized_pnl).label("avg_pnl"),
        )
        .where(
            JournalEntry.user_id == user.id,
            JournalEntry.emotion_before.is_not(None),
        )
        .group_by(JournalEntry.emotion_before)
        .order_by(func.count(JournalEntry.id).desc())
    )

    after_result = await db.execute(
        select(
            JournalEntry.emotion_after,
            func.count(JournalEntry.id).label("cnt"),
            func.avg(JournalEntry.realized_pnl).label("avg_pnl"),
        )
        .where(
            JournalEntry.user_id == user.id,
            JournalEntry.emotion_after.is_not(None),
        )
        .group_by(JournalEntry.emotion_after)
        .order_by(func.count(JournalEntry.id).desc())
    )

    before_rows = before_result.all()
    after_rows = after_result.all()

    return EmotionAnalyticsOut(
        before=[
            EmotionCount(emotion=r.emotion_before, count=r.cnt, avg_pnl=r.avg_pnl)
            for r in before_rows
        ],
        after=[
            EmotionCount(emotion=r.emotion_after, count=r.cnt, avg_pnl=r.avg_pnl)
            for r in after_rows
        ],
        total_entries=total,
    )


@router.get("/", response_model=JournalListResponse)
async def list_journal(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(default=None, description="Full-text search in notes and lesson"),
    stock_id: int | None = Query(default=None),
    start_date: str | None = Query(default=None, description="ISO date YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="ISO date YYYY-MM-DD"),
    emotion_before: str | None = Query(default=None),
    emotion_after: str | None = Query(default=None),
    entry_type: str | None = Query(default=None, description="auto | manual"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JournalListResponse:
    """List journal entries with optional full-text search and filters."""
    base = select(JournalEntry).where(JournalEntry.user_id == user.id)

    if q:
        base = base.where(
            text(
                "to_tsvector('english', coalesce(journal_entries.notes, '') || ' '"
                " || coalesce(journal_entries.lesson, '')) "
                "@@ plainto_tsquery('english', :q)"
            ).bindparams(q=q)
        )
    if stock_id is not None:
        base = base.where(JournalEntry.stock_id == stock_id)
    if start_date:
        base = base.where(JournalEntry.trade_date >= date.fromisoformat(start_date))
    if end_date:
        base = base.where(JournalEntry.trade_date <= date.fromisoformat(end_date))
    if emotion_before:
        base = base.where(JournalEntry.emotion_before == emotion_before)
    if emotion_after:
        base = base.where(JournalEntry.emotion_after == emotion_after)
    if entry_type:
        base = base.where(JournalEntry.entry_type == entry_type)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = int(count_result.scalar() or 0)

    page_result = await db.execute(
        base.order_by(JournalEntry.trade_date.desc(), JournalEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = page_result.scalars().all()
    enriched = [_enrich(e, await _symbol(db, e.stock_id)) for e in entries]
    return JournalListResponse(total=total, entries=enriched)


@router.post("/", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
async def create_entry(
    req: JournalEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalEntryOut:
    """Create a manual journal entry."""
    entry = JournalEntry(
        user_id=user.id,
        position_id=req.position_id,
        stock_id=req.stock_id,
        trade_date=req.trade_date,
        side=req.side,
        entry_price=req.entry_price,
        exit_price=req.exit_price,
        quantity=req.quantity,
        realized_pnl=req.realized_pnl,
        notes=req.notes,
        lesson=req.lesson,
        emotion_before=req.emotion_before,
        emotion_after=req.emotion_after,
        tags=req.tags,
        screenshot_paths=[],
        entry_type="manual",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _enrich(entry, await _symbol(db, entry.stock_id))


@router.get("/{entry_id}", response_model=JournalEntryOut)
async def get_entry(
    entry_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalEntryOut:
    entry = await db.get(JournalEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return _enrich(entry, await _symbol(db, entry.stock_id))


@router.put("/{entry_id}", response_model=JournalEntryOut)
async def update_entry(
    entry_id: str,
    req: JournalEntryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalEntryOut:
    entry = await db.get(JournalEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    entry.updated_at = datetime.now(tz=_IST)

    await db.commit()
    await db.refresh(entry)
    return _enrich(entry, await _symbol(db, entry.stock_id))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    entry = await db.get(JournalEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    # Delete screenshot files from disk
    screenshots_dir = _uploads_dir(user.id, entry_id)
    if screenshots_dir.exists():
        for f in screenshots_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            screenshots_dir.rmdir()
        except OSError:
            pass

    await db.delete(entry)
    await db.commit()


@router.post("/{entry_id}/screenshots", response_model=JournalEntryOut)
async def upload_screenshot(
    entry_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> JournalEntryOut:
    """Upload a screenshot and attach it to the journal entry."""
    entry = await db.get(JournalEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type '{content_type}'. Allowed: jpeg, png, webp, gif",
        )

    data = await file.read()
    if len(data) > settings.max_screenshot_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_screenshot_bytes // 1_048_576} MB limit",
        )

    ext = Path(file.filename or "img.jpg").suffix or ".jpg"
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = _uploads_dir(user.id, entry_id) / safe_name
    dest.write_bytes(data)

    url_path = f"/uploads/screenshots/{user.id}/{entry_id}/{safe_name}"
    paths: list[str] = list(entry.screenshot_paths or [])
    paths.append(url_path)
    entry.screenshot_paths = paths
    entry.updated_at = datetime.now(tz=_IST)

    await db.commit()
    await db.refresh(entry)
    return _enrich(entry, await _symbol(db, entry.stock_id))


@router.delete("/{entry_id}/screenshots/{filename}", response_model=JournalEntryOut)
async def delete_screenshot(
    entry_id: str,
    filename: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalEntryOut:
    """Remove a screenshot from a journal entry and delete the file."""
    entry = await db.get(JournalEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    url_path = f"/uploads/screenshots/{user.id}/{entry_id}/{filename}"
    paths: list[str] = [p for p in (entry.screenshot_paths or []) if p != url_path]

    if len(paths) == len(entry.screenshot_paths or []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found in this entry"
        )

    disk_path = _uploads_dir(user.id, entry_id) / filename
    disk_path.unlink(missing_ok=True)

    entry.screenshot_paths = paths
    entry.updated_at = datetime.now(tz=_IST)

    await db.commit()
    await db.refresh(entry)
    return _enrich(entry, await _symbol(db, entry.stock_id))
