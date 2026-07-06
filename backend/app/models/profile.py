"""Strategy profiles — versioned config rows for the four style engines
(Phase 2 slice 4).

A profile version is IMMUTABLE: edits insert (key, version+1) and flip the
old row to status='superseded' — never UPDATE config columns in place.
Signals and walk-forward goldens reference the exact version row, so
history can never drift underneath them. The partial unique index (one
non-superseded row per key) is enforced by the database, not by service
discipline.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    style: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    schedule: Mapped[str] = mapped_column(String(16), nullable=False)
    universe_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    setup_conditions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    weight_multipliers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    min_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    risk_template: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validity_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="inactive")
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_strategy_profiles_key_version"),
        # One non-superseded row per key — DB-enforced versioning invariant.
        Index(
            "uq_strategy_profiles_current",
            "key",
            unique=True,
            postgresql_where="status <> 'superseded'",
        ),
        Index("idx_strategy_profiles_dispatch", "status", "schedule"),
    )

    def __repr__(self) -> str:
        return f"<StrategyProfile {self.key} v{self.version} [{self.status}]>"
