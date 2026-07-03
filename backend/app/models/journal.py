"""JournalEntry model — Phase 10."""

import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)

EMOTIONS_BEFORE: frozenset[str] = frozenset(
    {"fear", "neutral", "confident", "greed", "anxious"}
)
EMOTIONS_AFTER: frozenset[str] = frozenset(
    {"regret", "satisfied", "neutral", "excited", "frustrated"}
)


class JournalEntry(Base):
    """One journal entry per trade (auto from closed position) or manual note."""

    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)          # 'LONG' | 'SHORT'
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    emotion_after: Mapped[str | None] = mapped_column(String(16), nullable=True)
    screenshot_paths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entry_type: Mapped[str] = mapped_column(String(8), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<JournalEntry id={self.id[:8]}… user={self.user_id} "
            f"date={self.trade_date} type={self.entry_type}>"
        )
