from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.stock import StockRead

# ---------------------------------------------------------------------------
# Filter spec
# ---------------------------------------------------------------------------

ALLOWED_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "between", "like", "in"}
ALLOWED_LOGIC = {"AND", "OR"}


class FilterSpec(BaseModel):
    field: str
    op: str
    value: Any

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        if v not in ALLOWED_OPS:
            raise ValueError(f"op must be one of {ALLOWED_OPS}")
        return v


class ScreenerRequest(BaseModel):
    filters: list[FilterSpec] = []
    logic: str = "AND"
    category_ids: list[int] | None = None  # AND-filter: stock must be in all given categories
    sort_by: str = "symbol"
    sort_dir: str = "asc"
    limit: int = 50
    offset: int = 0

    @field_validator("logic")
    @classmethod
    def validate_logic(cls, v: str) -> str:
        if v not in ALLOWED_LOGIC:
            raise ValueError("logic must be AND or OR")
        return v

    @field_validator("sort_dir")
    @classmethod
    def validate_sort_dir(cls, v: str) -> str:
        if v not in {"asc", "desc"}:
            raise ValueError("sort_dir must be asc or desc")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if not (1 <= v <= 200):
            raise ValueError("limit must be between 1 and 200")
        return v


class ScreenerResult(BaseModel):
    items: list[StockRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Saved screens
# ---------------------------------------------------------------------------


class SavedScreenCreate(BaseModel):
    name: str
    filter_spec: ScreenerRequest


class SavedScreenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    filter_spec: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Field catalog (with coverage)
# ---------------------------------------------------------------------------


class ScreenerFieldInfo(BaseModel):
    """One filterable field, plus how much of the universe it actually covers."""

    field: str
    field_type: str
    allowed_ops: list[str]
    available: bool
    note: str
    # Active stocks with a non-null value. None when coverage is not meaningful
    # (an unavailable field has no real column behind it). A field whose
    # `populated` is far below `total_active_stocks` will silently match almost
    # nothing — the UI is expected to say so rather than return an empty table.
    populated: int | None = None


class ScreenerFieldsResponse(BaseModel):
    total_active_stocks: int
    fields: list[ScreenerFieldInfo]
