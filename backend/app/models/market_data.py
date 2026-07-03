from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class Ohlcv1m(Base):
    """1-minute OHLCV — TimescaleDB hypertable."""

    __tablename__ = "ohlcv_1m"

    time: Mapped[datetime] = mapped_column(TZ, nullable=False, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821


class Ohlcv5m(Base):
    """5-minute OHLCV — TimescaleDB hypertable."""

    __tablename__ = "ohlcv_5m"

    time: Mapped[datetime] = mapped_column(TZ, nullable=False, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821


class Ohlcv15m(Base):
    """15-minute OHLCV — TimescaleDB hypertable."""

    __tablename__ = "ohlcv_15m"

    time: Mapped[datetime] = mapped_column(TZ, nullable=False, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821


class Ohlcv1h(Base):
    """1-hour OHLCV — TimescaleDB hypertable."""

    __tablename__ = "ohlcv_1h"

    time: Mapped[datetime] = mapped_column(TZ, nullable=False, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821


class OhlcvDaily(Base):
    """Daily OHLCV candle — TimescaleDB hypertable partitioned by time."""

    __tablename__ = "ohlcv_1d"

    time: Mapped[datetime] = mapped_column(TZ, nullable=False, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<OhlcvDaily stock_id={self.stock_id} time={self.time.date()}>"


class FiiDiiDaily(Base):
    """Daily FII/DII institutional flow — fetched from NSE."""

    __tablename__ = "fii_dii_daily"

    trade_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)
    investor_type: Mapped[str] = mapped_column(String(8), nullable=False, primary_key=True)
    segment: Mapped[str] = mapped_column(String(16), nullable=False, primary_key=True)
    buy_value_cr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sell_value_cr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<FiiDiiDaily date={self.trade_date} type={self.investor_type}"
            f" seg={self.segment}>"
        )


class BulkBlockDeal(Base):
    """Per-stock bulk / block deals from NSE and BSE."""

    __tablename__ = "bulk_block_deals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    deal_type: Mapped[str] = mapped_column(String(8), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )

    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "stock_id", "deal_type", "client_name", "transaction",
            "quantity", "price", "source",
            name="uq_bulk_block_deal",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BulkBlockDeal id={self.id} stock_id={self.stock_id}"
            f" type={self.deal_type} date={self.trade_date}>"
        )
