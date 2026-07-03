"""Pydantic schemas for Phase 8 paper trading endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

# ── Order schemas ─────────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    signal_id: str
    side: str = "BUY"      # 'BUY' | 'SELL'
    quantity: int | None = None  # override signal's suggested_qty if provided

    @field_validator("side")
    @classmethod
    def _side_upper(cls, v: str) -> str:
        v = v.upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    signal_id: str | None
    stock_id: int
    symbol: str = ""
    mode: str
    side: str
    order_type: str
    quantity: int
    price: Decimal | None
    status: str
    placed_at: datetime
    filled_at: datetime | None
    filled_price: Decimal | None
    filled_qty: int | None
    error_message: str | None


# ── Position schemas ───────────────────────────────────────────────────────────

class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    stock_id: int
    symbol: str = ""
    mode: str
    side: str
    quantity: int
    avg_entry_price: Decimal
    current_sl: Decimal | None
    current_tp: Decimal | None
    trail_state: str
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    opened_at: datetime
    closed_at: datetime | None
    signal_id: str | None


class PositionListResponse(BaseModel):
    total: int
    positions: list[PositionOut]


class ClosePositionRequest(BaseModel):
    exit_price: Decimal | None = None  # if None, use current market price


class UpdateSlRequest(BaseModel):
    new_sl: Decimal

    @field_validator("new_sl")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("new_sl must be positive")
        return v


# ── Daily P&L / circuit breaker ───────────────────────────────────────────────

class DailyPnlOut(BaseModel):
    trade_date: str        # YYYY-MM-DD in IST
    realized_pnl: Decimal
    open_count: int
    closed_count: int
    circuit_breaker_triggered: bool
    daily_loss_limit_inr: Decimal
    trades_taken_today: int
    max_trades_per_day: int


# ── Trade history ─────────────────────────────────────────────────────────────

class TradeHistoryResponse(BaseModel):
    total: int
    positions: list[PositionOut]
