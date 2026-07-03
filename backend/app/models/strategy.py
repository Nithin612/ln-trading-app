from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)


class StrategyRun(Base):
    """Saved backtest run — one row per executed strategy configuration."""

    __tablename__ = "strategy_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    factor_weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    universe: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="done")

    # Config
    capital: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    risk_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Summary metrics
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    losing_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    total_pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    avg_pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    avg_rr: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sharpe: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    sortino: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    avg_holding_days: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Ranking (lower = better when sorted by Sharpe desc)
    ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detailed data for charts
    equity_curve: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    trades_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<StrategyRun id={self.id} name={self.name!r} trades={self.total_trades}>"
