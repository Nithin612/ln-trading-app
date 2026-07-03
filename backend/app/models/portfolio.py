"""Portfolio models — Phase 11.

MfImportBatch: one batch per CAMS CAS upload.
MfHolding: individual scheme holding within a batch.
ManualAsset: gold, FDs, PPF, NPS, bonds, real estate, other.
"""

import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)

MANUAL_ASSET_TYPES: frozenset[str] = frozenset(
    {"gold", "fd", "ppf", "nps", "bonds", "real_estate", "other"}
)


class MfImportBatch(Base):
    """One import batch per CAMS CAS PDF upload."""

    __tablename__ = "mf_import_batches"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    investor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(12), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    total_holdings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    holdings: Mapped[list["MfHolding"]] = relationship(
        "MfHolding", back_populates="batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<MfImportBatch id={self.id[:8]}… user={self.user_id} "
            f"holdings={self.total_holdings} value={self.total_value}>"
        )


class MfHolding(Base):
    """One mutual-fund scheme holding within an import batch."""

    __tablename__ = "mf_holdings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("mf_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amc_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scheme_name: Mapped[str] = mapped_column(String(300), nullable=False)
    folio_number: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    batch: Mapped["MfImportBatch"] = relationship("MfImportBatch", back_populates="holdings")

    def __repr__(self) -> str:
        return (
            f"<MfHolding {self.scheme_name!r} folio={self.folio_number} "
            f"units={self.units} nav={self.nav}>"
        )


class ManualAsset(Base):
    """User-entered external asset: gold, FD, PPF, NPS, bonds, etc."""

    __tablename__ = "manual_assets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(_uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    purchase_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    units: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<ManualAsset id={self.id[:8]}… user={self.user_id} "
            f"type={self.asset_type} name={self.name!r} value={self.current_value}>"
        )
