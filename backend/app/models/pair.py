"""Pair-trading signals (Phase 6.5b) — the market-neutral SHADOW layer.

A `PairSignal` is a 2-leg market-neutral signal on a cointegrated pair's spread
(s = A − (α + β·B)): enter when the spread's z-score is extreme, exit as it reverts
toward the mean, stop if it diverges further. **SHADOW-ONLY** (`is_shadow` always True):
scored and measured to outcome from the tape, but NEVER tradeable — there is no
single-name order path for a spread, and an overnight pair short needs stock futures
(Phase 7). This table is purely ADDITIVE: it does not touch the single-name `signals`
table, the confluence engine, the paper broker, or the live order path. Nothing on the
live paper surface changes; pair signals accrue here and surface only in a report.

Both screening arms mint here — `method` in {"df", "adf"} — so the forward spread P&L
resolves the df-vs-adf A/B by evidence rather than argument.
"""

import uuid as _uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy import Index as SaIndex
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class PairSignal(Base):
    """One market-neutral pair entry (long/short the spread of a cointegrated pair).
    Pure observability — mints no order, feeds no P&L; measured to outcome in place."""

    __tablename__ = "pair_signals"
    __table_args__ = (
        SaIndex("idx_pair_signals_status", "status"),
        SaIndex("idx_pair_signals_method_created", "method", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    # The two legs. FK to stocks; a pair is (A, B) with the hedge ratio β below.
    stock_a_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    stock_b_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Which screening arm minted this — the df-vs-adf A/B (both run as shadow arms).
    method: Mapped[str] = mapped_column(String(8), nullable=False)  # "df" | "adf"

    # Hedge + mean-reversion profile at mint (from pair_screen.PairStat). Stats are
    # indicator-class f64. spread_entry / spread_sigma are price-derived → Numeric.
    beta: Mapped[float] = mapped_column(Float, nullable=False)  # A ≈ α + β·B
    alpha: Mapped[float] = mapped_column(Float, nullable=False)
    half_life: Mapped[float] = mapped_column(Float, nullable=False)
    df_tstat: Mapped[float] = mapped_column(Float, nullable=False)
    adf_pvalue: Mapped[float | None] = mapped_column(Float, nullable=True)

    # The trade. direction: "long_spread" = long A / short B (spread cheap, z ≤ −entry);
    # "short_spread" = short A / long B (spread rich, z ≥ +entry). Exit toward z≈z_exit,
    # stop at z_stop. Risk (for R) = |z_stop − entry_z| in z-units.
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_z: Mapped[float] = mapped_column(Float, nullable=False)
    z_exit: Mapped[float] = mapped_column(Float, nullable=False)
    z_stop: Mapped[float] = mapped_column(Float, nullable=False)
    spread_entry: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    spread_sigma: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    is_shadow: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    # Lifecycle: open → tp_first (reverted to z_exit) | sl_first (hit z_stop) |
    # expired (validity lapsed before either). Set by the spread-outcome tracker.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    validity_until: Mapped[datetime] = mapped_column(TZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    # Outcome (filled by the spread-outcome tracker — 6.5b slice 3). NULL until resolved.
    resolved_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    exit_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_exit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    # Realized P&L in R = (favourable z-move)/(|z_stop − entry_z| risk), so it is directly
    # comparable to the single-name attribution's R. NULL until resolved.
    outcome_r: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)

    stock_a: Mapped["Stock"] = relationship("Stock", foreign_keys=[stock_a_id])  # type: ignore[name-defined]  # noqa: F821
    stock_b: Mapped["Stock"] = relationship("Stock", foreign_keys=[stock_b_id])  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<PairSignal {self.id[:8]}… {self.method} {self.direction} "
            f"z={self.entry_z:+.2f} [{self.status}]>"
        )
