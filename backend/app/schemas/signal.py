"""Pydantic schemas for Signal endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class FactorScoreSchema(BaseModel):
    weight: float
    score: float
    explanation: str


class SignalOut(BaseModel):
    id: str
    stock_id: int
    symbol: str = ""          # joined from stock
    direction: str
    classification: str
    timeframe: str
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    suggested_qty: int
    confidence_pct: int
    factor_scores: dict[str, Any]
    triggering_patterns: list[str] | None
    triggering_indicators: list[str] | None
    headline: str
    status: str
    validity_until: datetime
    created_at: datetime
    # Presentation overlay (engine unchanged): how many active signals for this
    # (stock, direction) were collapsed into this one (base + profiles); and
    # whether ≥80% of the validity window has elapsed (stale — little runway).
    sources_count: int = 1
    near_expiry: bool = False
    days_valid_remaining: float = 0.0  # calendar days until validity_until (server-computed)
    # Daily Kaufman efficiency ratio (0-1): >~0.4 clean trend, <~0.3 choppy.
    # The 07-30/31 review showed choppy tapes drove ~all the losses.
    regime_er: float | None = None
    choppy: bool = False

    model_config = {"from_attributes": True}


class SignalListResponse(BaseModel):
    total: int
    signals: list[SignalOut]


class SignalOutcomeOut(BaseModel):
    """Tick-level outcome record (slice 3.6) — observability only."""

    signal_id: str
    stock_id: int
    direction: str
    classification: str
    timeframe: str
    validity_until: datetime
    status: str
    entry_touched_at: datetime | None
    entry_touch_price: Decimal | None
    sl_touched_at: datetime | None
    sl_touch_price: Decimal | None
    tp_touched_at: datetime | None
    tp_touch_price: Decimal | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
