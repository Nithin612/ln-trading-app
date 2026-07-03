"""Corporate filings model — Phase 6."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = DateTime(timezone=True)

FILING_TYPES = (
    "board_meeting",
    "earnings",
    "dividend",
    "split",
    "bonus",
    "merger",
    "agm",
    "rating_change",
    "other",
)

HIGH_IMPACT_TYPES = frozenset({"earnings", "merger", "rating_change"})


class CorporateFiling(Base):
    """NSE/BSE corporate announcement stored for the filings feed and event guard."""

    __tablename__ = "corporate_filings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    filing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_time: Mapped[datetime] = mapped_column(TZ, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    stock: Mapped["Stock"] = relationship("Stock")  # type: ignore[name-defined]  # noqa: F821

    @property
    def is_high_impact(self) -> bool:
        return self.filing_type in HIGH_IMPACT_TYPES

    def __repr__(self) -> str:
        return (
            f"<CorporateFiling id={self.id} stock_id={self.stock_id} "
            f"type={self.filing_type} source={self.source}>"
        )
