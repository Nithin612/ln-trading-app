"""Pydantic schemas for corporate filings endpoints — Phase 6."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class FilingOut(BaseModel):
    id: int
    stock_id: int
    symbol: str = ""          # joined from stock
    filing_type: str
    headline: str
    body: str | None
    filing_date: date
    filing_time: datetime
    source: str
    source_url: str | None
    sentiment_score: Decimal | None
    is_high_impact: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FilingListResponse(BaseModel):
    total: int
    filings: list[FilingOut]


class EventGuardStatus(BaseModel):
    """Response for per-stock event guard check."""

    stock_id: int
    symbol: str
    suppressed: bool
    reason: str | None        # e.g. "earnings filed 23 minutes ago"
    suppressed_until: datetime | None
