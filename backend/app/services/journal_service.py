"""Journal service — Phase 10.

Provides auto-population of journal entries when paper positions are closed.
Called from both the trading API endpoint and the position monitor task so
all close paths produce an entry.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.models.trading import Position

_IST = ZoneInfo("Asia/Kolkata")


async def auto_create_journal_entry(db: AsyncSession, position: Position) -> JournalEntry | None:
    """Create an auto journal entry for a just-closed position if one doesn't exist.

    Safe to call multiple times — skips creation if an auto entry for this
    position_id already exists.
    """
    if position.closed_at is None:
        return None

    existing = await db.execute(
        select(JournalEntry).where(
            JournalEntry.position_id == position.id,
            JournalEntry.entry_type == "auto",
        )
    )
    if existing.scalar_one_or_none():
        return None

    trade_date = position.closed_at.astimezone(_IST).date()

    entry = JournalEntry(
        user_id=position.user_id,
        position_id=position.id,
        stock_id=position.stock_id,
        trade_date=trade_date,
        side=position.side,
        entry_price=position.avg_entry_price,
        exit_price=None,   # caller may update after flush if needed
        quantity=position.quantity,
        realized_pnl=position.realized_pnl,
        notes=None,
        lesson=None,
        emotion_before=None,
        emotion_after=None,
        screenshot_paths=[],
        tags=[],
        entry_type="auto",
    )
    db.add(entry)
    await db.flush()
    return entry
