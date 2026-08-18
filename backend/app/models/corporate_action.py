"""Corporate-action model — Phase 6.8.5.

A STRUCTURED corporate action (split/bonus) with a verified ratio and ex-date —
distinct from the `corporate_filings` announcement feed (headline text, no ratio)
and the `ca_detector` gap heuristic (flags a stock, no ratio). The ratio here is
entered/verified by a human (admin), never guessed from a price gap or parsed
from headline text: a wrong ratio silently corrupts a held position's P&L and R.

The ex-date worker (`services/ca_adjust.py`) reads these to adjust OPEN paper
positions on the ex-date, R-preservingly (price levels ÷ factor, qty × factor).
`PositionCorporateAction` is the idempotency ledger + audit: one row per
(position, action), UNIQUE — so a re-run can never double-adjust.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)

CA_TYPES = ("split", "bonus")


class CorporateAction(Base):
    """A verified split/bonus. Ratio is `ratio_from : ratio_to` shares — a 5:1
    split is 1→5 (`ratio_from=1, ratio_to=5`); a 1:1 bonus is 1→2 (a holder ends
    with 2 shares per 1 held). The share multiplier `factor = ratio_to/ratio_from`
    (>1 for both a split and a bonus)."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        # One event per (stock, ex-date, type) — dup entry is a mistake, not data.
        UniqueConstraint(
            "stock_id", "ex_date", "action_type", name="uq_corporate_action_event"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)  # split | bonus
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Ratio as new:old shares. Both > 0. See class docstring.
    ratio_from: Mapped[int] = mapped_column(Integer, nullable=False)  # shares held
    ratio_to: Mapped[int] = mapped_column(Integer, nullable=False)  # shares after
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    @property
    def factor(self) -> Decimal:
        """Share multiplier: qty × factor, price levels ÷ factor."""
        return Decimal(self.ratio_to) / Decimal(self.ratio_from)

    def __repr__(self) -> str:
        return (
            f"<CorporateAction id={self.id} stock_id={self.stock_id} "
            f"{self.action_type} {self.ratio_from}:{self.ratio_to} ex={self.ex_date}>"
        )


class PositionCorporateAction(Base):
    """Idempotency ledger + audit: this position was adjusted for this action.
    UNIQUE (position_id, corporate_action_id) makes double-adjust impossible; the
    before/after fields make the adjustment reconstructable and reversible."""

    __tablename__ = "position_corporate_actions"
    __table_args__ = (
        UniqueConstraint(
            "position_id", "corporate_action_id", name="uq_position_corporate_action"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("positions.id", ondelete="CASCADE"), nullable=False
    )
    corporate_action_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("corporate_actions.id", ondelete="CASCADE"), nullable=False
    )
    factor: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    old_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    new_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    old_avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    new_avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<PositionCorporateAction pos={self.position_id[:8]}… "
            f"ca={self.corporate_action_id} {self.old_quantity}→{self.new_quantity}>"
        )
