from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    exchange: str
    isin: str | None
    company_name: str
    sector: str | None
    industry: str | None
    market_cap_cr: Decimal | None
    lot_size: int
    tick_size: Decimal
    is_fno: bool
    is_nifty50: bool
    is_banknifty: bool
    is_finnifty: bool
    is_active: bool
    listed_on: date | None
    created_at: datetime
    updated_at: datetime


class StockListParams(BaseModel):
    q: str | None = None          # fuzzy search on symbol / company_name
    sector: str | None = None
    is_nifty50: bool | None = None
    is_banknifty: bool | None = None
    is_finnifty: bool | None = None
    is_fno: bool | None = None
    is_active: bool | None = True
    sort_by: str = "symbol"
    sort_dir: str = "asc"
    page: int = 1
    page_size: int = 50


class StockListResponse(BaseModel):
    items: list[StockRead]
    total: int
    page: int
    page_size: int
    pages: int
