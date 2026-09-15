"""Pydantic schemas for corporate actions — Phase 6.8.5."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.corporate_action import CA_TYPES


class CorporateActionCreate(BaseModel):
    """Admin-entered, verified split/bonus. Ratio is new:old shares — a 5:1 split
    is `ratio_from=1, ratio_to=5`; a 1:1 bonus is `1:2`."""

    stock_id: int
    action_type: str
    ex_date: date
    ratio_from: int = Field(gt=0)
    ratio_to: int = Field(gt=0)
    note: str | None = None

    @field_validator("action_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in CA_TYPES:
            raise ValueError(f"action_type must be one of {CA_TYPES}")
        return v


class CorporateActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    action_type: str
    ex_date: date
    ratio_from: int
    ratio_to: int
    source: str
    note: str | None = None


class CaQuarantineOut(BaseModel):
    """One stock currently held out of every suggestion universe by the CA detector."""

    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    symbol: str
    flagged_at: datetime
    reason: str | None
    is_active: bool


class CaClearRequest(BaseModel):
    """⚠ `reason` is REQUIRED and non-trivial on purpose. The clear is a human assertion
    that the unadjusted history is safe to score again, and "cleared" with no
    justification is not an audit trail — it is the same monotonic-accumulator problem
    one step later, where nobody can tell a reviewed release from a careless one."""

    reason: str = Field(min_length=10, max_length=2000)


class CaFlagEventOut(BaseModel):
    """One entry in the append-only quarantine log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    event: str
    at: datetime
    reason: str
    actor_user_id: int | None
