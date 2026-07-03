"""Pydantic schemas for the trading journal — Phase 10."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

EMOTIONS_BEFORE = frozenset({"fear", "neutral", "confident", "greed", "anxious"})
EMOTIONS_AFTER = frozenset({"regret", "satisfied", "neutral", "excited", "frustrated"})


class JournalEntryCreate(BaseModel):
    stock_id: int | None = None
    position_id: str | None = None
    trade_date: date
    side: str | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    quantity: int | None = None
    realized_pnl: Decimal | None = None
    notes: str | None = None
    lesson: str | None = None
    emotion_before: str | None = None
    emotion_after: str | None = None
    tags: list[str] = []

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str | None) -> str | None:
        if v is not None and v not in ("LONG", "SHORT"):
            raise ValueError("side must be LONG or SHORT")
        return v

    @field_validator("emotion_before")
    @classmethod
    def validate_emotion_before(cls, v: str | None) -> str | None:
        if v is not None and v not in EMOTIONS_BEFORE:
            raise ValueError(f"emotion_before must be one of {sorted(EMOTIONS_BEFORE)}")
        return v

    @field_validator("emotion_after")
    @classmethod
    def validate_emotion_after(cls, v: str | None) -> str | None:
        if v is not None and v not in EMOTIONS_AFTER:
            raise ValueError(f"emotion_after must be one of {sorted(EMOTIONS_AFTER)}")
        return v


class JournalEntryUpdate(BaseModel):
    trade_date: date | None = None
    side: str | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    quantity: int | None = None
    realized_pnl: Decimal | None = None
    notes: str | None = None
    lesson: str | None = None
    emotion_before: str | None = None
    emotion_after: str | None = None
    tags: list[str] | None = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str | None) -> str | None:
        if v is not None and v not in ("LONG", "SHORT"):
            raise ValueError("side must be LONG or SHORT")
        return v

    @field_validator("emotion_before")
    @classmethod
    def validate_emotion_before(cls, v: str | None) -> str | None:
        if v is not None and v not in EMOTIONS_BEFORE:
            raise ValueError(f"emotion_before must be one of {sorted(EMOTIONS_BEFORE)}")
        return v

    @field_validator("emotion_after")
    @classmethod
    def validate_emotion_after(cls, v: str | None) -> str | None:
        if v is not None and v not in EMOTIONS_AFTER:
            raise ValueError(f"emotion_after must be one of {sorted(EMOTIONS_AFTER)}")
        return v


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    position_id: str | None
    stock_id: int | None
    symbol: str | None = None
    trade_date: date
    side: str | None
    entry_price: Decimal | None
    exit_price: Decimal | None
    quantity: int | None
    realized_pnl: Decimal | None
    notes: str | None
    lesson: str | None
    emotion_before: str | None
    emotion_after: str | None
    screenshot_paths: list[str]
    tags: list[str]
    entry_type: str
    created_at: datetime
    updated_at: datetime


class JournalListResponse(BaseModel):
    total: int
    entries: list[JournalEntryOut]


class EmotionCount(BaseModel):
    emotion: str
    count: int
    avg_pnl: Decimal | None


class EmotionAnalyticsOut(BaseModel):
    before: list[EmotionCount]
    after: list[EmotionCount]
    total_entries: int
