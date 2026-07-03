"""Broker-related models for Phase 7 — Kite Connect integration."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)


class BrokerToken(Base):
    """Stores Kite Connect access tokens per user.

    Tokens are valid until 6 AM IST the next day.  The OAuth flow writes here;
    the tick consumer reads the latest non-expired token.
    """

    __tablename__ = "broker_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker: Mapped[str] = mapped_column(String(32), nullable=False, default="kite")
    access_token: Mapped[str] = mapped_column(String(512), nullable=False)
    # request_token used to obtain this access_token (kept for audit trail)
    request_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TZ, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<BrokerToken id={self.id} user_id={self.user_id} broker={self.broker!r}>"


class KiteInstrument(Base):
    """Instrument metadata from Kite — maps exchange symbol to numeric instrument_token.

    Downloaded from Kite's instruments CSV endpoint each trading day.
    The tick consumer uses instrument_token to subscribe to ticks.
    """

    __tablename__ = "kite_instruments"

    instrument_token: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange_token: Mapped[int] = mapped_column(Integer, nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(16), nullable=False)  # EQ, FUT, CE, PE
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0")
    )
    tick_size: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.05")
    )
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    segment: Mapped[str] = mapped_column(String(32), nullable=False)
    # ISO date string e.g. "2024-11-28" for F&O expiries; empty for EQ
    expiry: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    synced_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<KiteInstrument {self.exchange}:{self.tradingsymbol}"
            f" token={self.instrument_token}>"
        )
