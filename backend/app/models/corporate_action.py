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


CA_FLAG_EVENTS = ("flagged", "cleared")


class CaFlagEvent(Base):
    """⭐ APPEND-ONLY history of the CA quarantine — every flag and every clear.

    **Why a log and not three columns on `stocks`.** `ca_flagged_at` is set by
    `ca_detector` and, once a clear exists, the same name can be flagged again — the
    detector only skips rows where `ca_flagged_at IS NULL`. A single
    `ca_cleared_at/_by/_reason` triple would therefore be OVERWRITTEN by the next flag,
    destroying the record of the review that preceded it. That is the same trap §41 named
    when it refused to drop `uq_stocks_symbol_exchange`: **the merge overwrites its own
    evidence**, and the rate of the thing you wanted to measure becomes unmeasurable
    retrospectively.

    **Why the quarantine needed a clear at all.** Measured 2026-09-14: 7 stocks flagged,
    5 of them active, **4 of the 7 flagged that same day** — so it accrues at roughly four
    a week with no way to empty it, while `stock.py`'s own docstring says "unflag via admin
    after verifying" and no such path existed anywhere (Q-R3: *the CA quarantine is a
    MONOTONIC ACCUMULATOR*).

    ⛔ **An EXPIRY was considered and rejected.** The contamination is in the unadjusted
    PRICE HISTORY, and that does not heal with time: a split's bars stay wrong until the
    series is adjusted or aged out of every indicator window. An expiry would silently
    re-admit contaminated history on a timer, which is worse than a flag nobody clears.
    A human verifying and saying why is the only honest clear.
    """

    __tablename__ = "ca_flag_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(16), nullable=False)
    at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    #: The detector's gap description when flagged; the reviewer's justification when
    #: cleared. Required on a clear — "cleared, no reason given" is not an audit trail.
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: NULL for a machine flag; the admin who reviewed it on a clear. The asymmetry is
    #: the point: a machine may quarantine, only a person may release.
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
