"""Signal engine models — Phase 5."""

import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class SrLevel(Base):
    """Support/Resistance lines and demand/supply zones computed by the analysis engine."""

    __tablename__ = "sr_levels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    level_type: Mapped[str] = mapped_column(String(16), nullable=False)
    price_lower: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    price_upper: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_touched_at: Mapped[datetime] = mapped_column(TZ, nullable=False)
    last_touched_at: Mapped[datetime] = mapped_column(TZ, nullable=False)
    is_broken: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    broken_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SrLevel id={self.id} stock_id={self.stock_id} "
            f"type={self.level_type} tf={self.timeframe}>"
        )


class Signal(Base):
    """Core output of the confluence engine — one row per signal emitted."""

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    entry_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    suggested_qty: Mapped[int] = mapped_column(Integer, nullable=False)

    confidence_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    triggering_patterns: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    triggering_indicators: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    headline: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    validity_until: Mapped[datetime] = mapped_column(TZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    expired_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    outcome_pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)

    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821
    outcome: Mapped["SignalOutcome | None"] = relationship(
        "SignalOutcome", back_populates="signal", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Signal id={self.id[:8]}… stock_id={self.stock_id} "
            f"{self.direction} {self.confidence_pct}%>"
        )


class SignalOutcome(Base):
    """EOD reconciliation result — did the signal hit TP or SL?"""

    __tablename__ = "signal_outcomes"

    signal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("signals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hit_target: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hit_sl: Mapped[bool] = mapped_column(Boolean, nullable=False)
    max_favorable_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    max_adverse_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    pnl_pct: Mapped[Decimal] = mapped_column(Numeric(7, 3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="outcome")

    def __repr__(self) -> str:
        return f"<SignalOutcome signal_id={self.signal_id[:8]}… pnl={self.pnl_pct}%>"


# StrategyRun moved to app.models.strategy in Phase 9.
