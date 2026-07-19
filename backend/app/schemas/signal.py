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
