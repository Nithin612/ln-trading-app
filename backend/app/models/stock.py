from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(16), nullable=True, unique=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Populated in Phase 4 from price × shares outstanding; NULL until then.
    market_cap_cr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tick_size: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.05")
    )

    is_fno: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_nifty50: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banknifty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_finnifty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Corporate-action quarantine (Phase 2 slice 6): unadjusted bhavcopy
    # history poisons indicator windows across a split/bonus — flagged
    # stocks are excluded from suggestion universes until reviewed.
    ca_flagged_at: Mapped[datetime | None] = mapped_column(TZ, nullable=True)
    ca_flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    index_memberships: Mapped[list["IndexConstituent"]] = relationship(
        "IndexConstituent", back_populates="stock", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),
    )

    def __repr__(self) -> str:
        return f"<Stock id={self.id} symbol={self.symbol!r} exchange={self.exchange!r}>"


class Index(Base):
    __tablename__ = "indices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    constituents: Mapped[list["IndexConstituent"]] = relationship(
        "IndexConstituent", back_populates="index", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Index symbol={self.symbol!r}>"


class IndexConstituent(Base):
    __tablename__ = "index_constituents"

    index_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("indices.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stocks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    weight_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    added_on: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False, server_default=func.current_date()
    )
    removed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    index: Mapped["Index"] = relationship("Index", back_populates="constituents")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="index_memberships")

    def __repr__(self) -> str:
        return f"<IndexConstituent index_id={self.index_id} stock_id={self.stock_id}>"


class SavedScreen(Base):
    __tablename__ = "saved_screens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    filter_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_saved_screens_user_name"),
    )

    def __repr__(self) -> str:
        return f"<SavedScreen id={self.id} user_id={self.user_id} name={self.name!r}>"
