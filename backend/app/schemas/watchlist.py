from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("name must not be empty")
    if len(v) > 64:
        raise ValueError("name must be at most 64 characters")
    return v


class WatchlistCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        return _clean_name(v)


class WatchlistUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        return _clean_name(v)


class WatchlistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    symbol: str
    company_name: str
    added_at: datetime


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemRead]


class StockRef(BaseModel):
    # int64-bounded at the edge: an unbounded JSON int reaches asyncpg as a
    # DataError (500) instead of a 404/422 (bug-hunter LOW, 2026-07-11).
    stock_id: int = Field(gt=0, lt=2**63)
