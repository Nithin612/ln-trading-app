"""Order and Position models — Phase 8 paper trading."""

import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class Order(Base):
    """Records a single paper (or live) order placement and fill."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(8), nullable=False)       # 'paper' | 'live'
    side: Mapped[str] = mapped_column(String(8), nullable=False)       # 'BUY' | 'SELL'
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'MARKET' | 'LIMIT' | 'SL'
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    trigger_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    placed_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    filled_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    filled_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    filled_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    broker_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id[:8]}… user={self.user_id} "
            f"{self.side} {self.quantity} @ {self.status}>"
        )


class Position(Base):
    """Tracks an open or closed paper/live position and its running P&L."""

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(8), nullable=False)       # 'paper' | 'live'
    side: Mapped[str] = mapped_column(String(8), nullable=False)       # 'LONG' | 'SHORT'
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    current_sl: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    current_tp: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    # none → breakeven → trailing_1 → trailing_2
    trail_state: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0")
    )
    opened_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    signal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    journal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    def __repr__(self) -> str:
        state = "open" if self.is_open else "closed"
        return (
            f"<Position id={self.id[:8]}… user={self.user_id} "
            f"{self.side} {self.quantity} @ {self.avg_entry_price} [{state}]>"
        )
