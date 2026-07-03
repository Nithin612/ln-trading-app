"""Pydantic schemas for Phase 9 — Strategy Lab."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field  # noqa: F401 — re-exported for IDE

# ── Request schemas ──────────────────────────────────────────────────────────

class RunBacktestRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    timeframe: str = Field(default="1d", pattern=r"^(1m|5m|15m|1h|1d)$")
    universe: str = Field(default="NIFTY50", min_length=1, max_length=64)
    period_start: datetime
    period_end: datetime
    capital: Decimal = Field(default=Decimal("100000"), gt=0)
    risk_pct: Decimal = Field(default=Decimal("2"), gt=0, le=10)
    min_confidence: int = Field(default=70, ge=0, le=100)
    weight_multipliers: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-group weight multipliers. Keys: pattern, trend, momentum, "
            "volume, structure, institutional. Values typically 0.5–2.0."
        ),
    )
    # Optional: explicit list of stock symbols to include (overrides universe)
    symbols: list[str] | None = None


class PresetScanRequest(BaseModel):
    timeframe: str = Field(default="1d", pattern=r"^(1m|5m|15m|1h|1d)$")
    universe: str = Field(default="NIFTY50", min_length=1, max_length=64)
    period_start: datetime
    period_end: datetime
    capital: Decimal = Field(default=Decimal("100000"), gt=0)
    risk_pct: Decimal = Field(default=Decimal("2"), gt=0, le=10)
    min_confidence: int = Field(default=70, ge=0, le=100)
    symbols: list[str] | None = None


# ── Response schemas ─────────────────────────────────────────────────────────

class TradeRecordOut(BaseModel):
    stock: str
    direction: str
    classification: str
    confidence_pct: int
    entry_date: str
    entry_price: float
    stop_loss: float
    take_profit: float
    qty: int
    exit_date: str | None
    exit_price: float | None
    pnl_pct: float | None
    hit_target: bool
    hit_sl: bool


class StrategyRunOut(BaseModel):
    id: int
    name: str
    description: str | None
    timeframe: str
    universe: str
    period_start: datetime
    period_end: datetime
    status: str
    factor_weights: dict[str, Any]
    capital: Decimal | None
    risk_pct: Decimal | None
    min_confidence: int | None

    total_trades: int
    winning_trades: int
    losing_trades: int | None
    win_rate_pct: Decimal | None
    total_pnl_pct: Decimal | None
    avg_pnl_pct: Decimal | None
    avg_rr: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    max_drawdown_pct: Decimal | None
    avg_holding_days: Decimal | None
    ranking: int | None

    equity_curve: list[float] | None
    trades_json: list[dict[str, Any]] | None

    created_at: datetime

    model_config = {"from_attributes": True}


class StrategyRunListResponse(BaseModel):
    total: int
    runs: list[StrategyRunOut]


class PresetScanEntry(BaseModel):
    preset_name: str
    weight_multipliers: dict[str, float]
    total_trades: int
    win_rate_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    avg_rr: float
    avg_holding_days: float
    equity_curve: list[float]


class PresetScanResponse(BaseModel):
    entries: list[PresetScanEntry]
