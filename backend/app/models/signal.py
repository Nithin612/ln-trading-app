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
from sqlalchemy import Index as SaIndex
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

    # Strategy-profile linkage (Phase 2 slice 4). profile_id pins the exact
    # version row; profile_key is denormalized so the active-suggestion
    # dedup index spans version bumps. NULL on legacy/non-profile signals.
    profile_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("strategy_profiles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    profile_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    setup_trigger: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # §4 volatility attribution (Phase-1 review carry-over): True when the
    # ATR>3% reduction changed suggested_qty; NULL = unknown (legacy rows).
    volatility_reduced: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

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
    """Signal-outcome tick evaluation (Phase 3, slice 3.6).

    One row per signal, recording FIRST tick-level touches of its entry
    zone, SL, and TP inside the validity window — "did the entry zone
    touch before expiry?" is the Phase-6 headline metric this feeds.
    Written by the outcome recorder (alerts-stream consumer group,
    durable at-least-once); finalized by the expiry sweeper. Replaces
    the v1 EOD-reconciliation shape, which no code ever wrote or read
    (0 rows; migration s5t6u7v8w9x0).

    Status ladder (monotonic TOWARD TRUTH — never back to a live state):
        open              → nothing touched yet
        entry_touched     → entry zone touched inside validity
        tp_first          → entry touched, then TP before SL
        sl_first          → entry touched, then SL before TP
        expired_untouched → validity lapsed, entry never touched
        expired_open      → lapsed after entry; neither SL nor TP
    Crash-window upgrades (recorder outage overlapping an expiry sweep;
    PEL-recovered IN-VALIDITY touches prove a better verdict):
        expired_untouched → expired_open (recovered entry touch)
        expired_open      → tp_first / sl_first (recovered SL/TP touch,
                            entry already proven)

    SL/TP touches WITHOUT a prior entry touch never resolve the outcome
    (a TP cross on a never-entered setup is a missed trade, not a win) —
    their first-touch stamps still record for Phase-6 honesty. Pure
    observability: never feeds scoring, sizing, gating, or backtests.

    KNOWN MEASUREMENT LIMITS (quant-verifier 2026-07-19; ruling queued —
    ledger §Decisions):
      - Cross triggers fire on OBSERVED side transitions only. Intra-
        session gaps through a level fire; an OVERNIGHT gap beyond SL/TP
        does not (the first tick of the day merely arms the side), so
        sl_first is a FLOOR and swing/positional tp_first may include
        gap-through-SL survivors. Candidate fixes (session-open
        reconciliation / Phase-6 candle cross-check) change recording
        semantics and await the user's ruling.
      - At-level asymmetry: cross_up fires AT the level, cross_down only
        strictly below — a BUY's exact tick AT the SL doesn't count while
        its TP-at-level does (SELL mirrored). Exchange stop orders
        trigger at LTP == trigger price; counting exact touches needs a
        Rust LevelKind addition + user sign-off (rules/rust.md semantic
        discipline).
      - Phase-6 hit-rates MUST cohort signals.created_at >= OUTCOME_EPOCH
        (straddler bias direction unknown — see services/signal_outcomes)."""

    __tablename__ = "signal_outcomes"
    __table_args__ = (
        SaIndex("idx_signal_outcomes_status", "status"),
        SaIndex("idx_signal_outcomes_class_status", "classification", "status"),
    )

    signal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("signals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized for Phase-6 aggregation (hit-rate by style/timeframe
    # without joining the growing signals table).
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    validity_until: Mapped[datetime] = mapped_column(TZ, nullable=False)

    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")

    entry_touched_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    entry_touch_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    sl_touched_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    sl_touch_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    tp_touched_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    tp_touch_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    signal: Mapped["Signal"] = relationship("Signal", back_populates="outcome")

    def __repr__(self) -> str:
        return f"<SignalOutcome {self.signal_id[:8]}… [{self.status}]>"


# StrategyRun moved to app.models.strategy in Phase 9.
