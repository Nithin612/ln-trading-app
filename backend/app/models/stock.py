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


class SymbolHistory(Base):
    """D1′ — the record of identity churn, which used to leave no trace.

    Two kinds exist and only one was handled. A RENAME (ISIN keeps, symbol changes)
    is applied in place by `seed_stocks.plan_renames` so the row keeps its id and
    with it every bar, signal and position — correct, but afterwards nothing
    recorded that the old ticker ever existed, so "what was this id called in July?"
    was unanswerable. That is half of why §20/2's reversal SQL is dangerous.

    REUSE (symbol keeps, ISIN changes — NSE re-issuing a delisted ticker) is the
    inverse, and it silently merged two companies into one row. ⚠ Its frequency
    cannot be measured retrospectively because the merge overwrites its own
    evidence, which is why this table RECORDS churn rather than restructuring
    around it: `uq_stocks_symbol_exchange` deliberately still stands.

    ⚠ `isin` is the anchor AS IT WAS, not as it is now. If a row's ISIN is later
    overwritten, this is the only surviving record of what it used to be.

    ⚠ Invariant: exactly one open interval (`valid_to IS NULL`) per `stock_id`,
    enforced by the writer — a partial unique index cannot express "one NULL per
    group" while the closed intervals share the same columns.
    """

    __tablename__ = "symbol_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 'seed' (first sight) | 'rename' (ISIN kept, ticker moved) | 'reuse' (ticker
    # kept, ISIN moved — a different company)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol", "exchange", "valid_from", name="uq_symbol_history_symbol_from"
        ),
    )

    def __repr__(self) -> str:
        span = f"{self.valid_from}..{self.valid_to or 'now'}"
        return f"<SymbolHistory stock_id={self.stock_id} {self.symbol!r} {span}>"


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


class IndexOhlcvDaily(Base):
    """Daily EOD OHLC for a market/sector index (MCE slice 2).

    The missing keystone for relative-strength context: the tradeable engine had no
    index price series (`indices` held only the registry + membership). Fed from the
    NSE indices bhavcopy CSV (the same `ind_close_all_*.csv` the India-VIX recorder
    already downloads — every NSE index sits in that one file), so no Kite dependency.
    Keyed on the existing `indices` registry; a plain table (a handful of indices ×
    daily bars), mirroring `india_vix_daily`."""

    __tablename__ = "index_ohlcv_1d"

    index_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("indices.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    def __repr__(self) -> str:
        return f"<IndexOhlcvDaily index_id={self.index_id} {self.trade_date} close={self.close}>"


class CasDaily(Base):
    """Closing-Auction-Session daily capture (CAS Stage 1) — one row per (stock, trade_date).

    Captured from Kite /quote during 3:15–3:35 IST by the market-hours task (cas_tasks.py):
    the pre-auction (3:15) price, the exchange reference price, the evolving indicative close, the
    final official/auction close, and the total imbalance quantity. Observability/research ONLY — it
    feeds the CAS overnight-reversal study (Stage 2) and never gates, sizes, or trades. `ohlc.close`
    from Kite is the PRIOR day's close mid-session, so the true close is `official_close` (the last
    price after the auction executes ~15:29), NOT ohlc.close."""

    __tablename__ = "cas_daily"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    pre_auction_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    indicative_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    official_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_imbalance_qty: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    polls: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<CasDaily stock_id={self.stock_id} {self.trade_date} "
            f"pre={self.pre_auction_price} close={self.official_close}>"
        )


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
