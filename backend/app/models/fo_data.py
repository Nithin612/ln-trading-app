"""F&O market-data models — Phase 0 recorders (UPGRADE_PLAN.md).

Recorded history is the scarce resource for options analytics (Kite has no
deep historical options data), so recording starts in Phase 0 even though
the analytics that consume it arrive in Phase 4:

  - FoBhavcopy:          NSE F&O EOD bhavcopy (UDiFF) — per-contract
                         close/settle/OI/volume; bootstraps IV-rank/PCR/
                         max-pain history from public archives.
  - IndiaVixDaily:       India VIX EOD — interim IV-regime proxy.
  - OptionChainSnapshot: intraday chain snapshots via kite.quote REST
                         (1-minute cadence; hypertable).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)


class FoBhavcopy(Base):
    """One row per contract per trading day from the NSE F&O bhavcopy."""

    __tablename__ = "fo_bhavcopy"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)  # underlying
    instrument: Mapped[str] = mapped_column(String(4), primary_key=True)  # FUT|CE|PE
    expiry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    strike: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), primary_key=True, default=Decimal("0")  # futures: 0
    )

    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    settle_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    underlying_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume_contracts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    open_interest: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_in_oi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class IndiaVixDaily(Base):
    """India VIX EOD values from the NSE indices bhavcopy."""

    __tablename__ = "india_vix_daily"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)


class OptionChainSnapshot(Base):
    """Intraday option-chain snapshot row (TimescaleDB hypertable on time)."""

    __tablename__ = "option_chain_snapshots"

    time: Mapped[datetime] = mapped_column(TZ, primary_key=True)
    instrument_token: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)  # underlying
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    strike: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    option_type: Mapped[str] = mapped_column(String(2), nullable=False)  # CE|PE|FU

    ltp: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    oi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
