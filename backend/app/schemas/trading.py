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
    unrealized_pnl: Decimal | None   # NET of estimated round-trip costs (open)
    realized_pnl: Decimal            # NET of charges once closed
    charges: Decimal | None = None   # round-trip trading costs (None = pre-cost history)
    exit_price: Decimal | None = None    # closing fill price (None while open)
    exit_reason: str | None = None       # sl_hit | tp_hit | manual (None while open)
    current_price: Decimal | None = None  # transient live/last price (open positions)
    peak_price: Decimal | None = None    # best price seen while open (MFE)
    peak_pnl: Decimal | None = None      # GROSS peak profit (max favourable excursion)
    opened_at: datetime
    closed_at: datetime | None
    signal_id: str | None


class PositionListResponse(BaseModel):
    total: int
    positions: list[PositionOut]


# ── Profit-lock shadow comparator (read-only evidence) ─────────────────────────

class ShadowPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy: str
    exit_price: Decimal | None
    exit_time: datetime | None
    exit_net: Decimal | None
    still_open: bool
    capture_pct: float | None


class ShadowComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: str
    symbol: str
    side: str
    quantity: int
    entry: Decimal
    original_sl: Decimal
    classification: str
    bars: int
    peak_price: Decimal | None
    peak_gross: Decimal | None
    actual_exit_price: Decimal | None
    actual_net: Decimal | None
    actual_capture_pct: float | None
    actual_exit_off_tape: bool = False
    policies: list[ShadowPolicyOut]
    note: str | None = None


class ShadowCompareResponse(BaseModel):
    total: int
    comparisons: list[ShadowComparisonOut]


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


# ── Paper record (the 30-day-clock view) ──────────────────────────────────────

class PaperDayRow(BaseModel):
    date: str              # YYYY-MM-DD in IST
    realized_pnl: Decimal  # NET of charges
    charges: Decimal
    trades: int            # positions closed that day
    profitable: bool       # net realized > 0
    cumulative_pnl: Decimal


class PaperRecordOut(BaseModel):
    """Per-IST-day realized-P&L history for the paper account — the visible
    surface of the 30-day profitable-paper gate (the authoritative gate stays
    Phase 7). P&L is net of trading costs."""

    days: list[PaperDayRow]        # chronological (oldest → newest)
    total_days_traded: int
    profitable_days: int
    losing_days: int
    current_streak: int            # consecutive most-recent profitable days
    best_streak: int
    total_realized_pnl: Decimal    # net
    total_charges: Decimal
    total_trades: int
    win_rate_pct: Decimal
    target_days: int = 30
    start_date: str | None = None
    last_date: str | None = None
