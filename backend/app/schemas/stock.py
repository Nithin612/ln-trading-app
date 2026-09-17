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


class ResolvedStockOut(BaseModel):
    """V4 — a search hit that explains itself."""

    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    symbol: str
    company_name: str
    #: Admitted by the universe rule — scannable and orderable at all.
    in_universe: bool
    #: ⚠ INDEPENDENT of `in_universe`: a quarantined name can be perfectly tradeable and
    #: still absent from every suggestion, which no other surface can explain.
    ca_quarantined: bool
    #: True only when BOTH hold — what `resolve_universe` actually requires.
    suggestible: bool
    exclusion_reasons: list[str] = []
    #: Tickers this row used to trade under (A7), newest first.
    former_symbols: list[str] = []
    #: The date the rule reason was justified from. `None` = the term could not be
    #: justified from a record, and the reason says only THAT it is excluded (A24).
    reason_as_of: date | None = None


class StockSearchResponse(BaseModel):
    query: str
    hits: list[ResolvedStockOut]
    #: Set when the query matched a FORMER ticker — "AEROPLANE (formerly AMIRCHAND)".
    matched_former_symbol: str | None = None


class DataCoverageOut(BaseModel):
    """V5 — whether the scan can even LOOK at this name."""

    daily_bars: int
    min_bars_to_score: int
    enough_history: bool
    #: How many more sessions it needs before the scan will score it at all.
    shortfall: int
    latest_bar: date | None = None


class StockEligibilityOut(BaseModel):
    """V5 / A2 tier 3 — why this stock does or does not produce signals.

    ⚠ The backend verdict is AUTHORITATIVE (§28: never let the frontend derive universe
    state). Every field here is computed by the same `stock_resolve` code the search
    surface uses, so the two cannot drift.
    """

    in_universe: bool
    ca_quarantined: bool
    #: BOTH of the above — what `resolve_universe` actually requires.
    suggestible: bool
    exclusion_reasons: list[str] = []
    reason_as_of: date | None = None
    coverage: DataCoverageOut
    #: True only when the name is suggestible AND has enough history to be scored. The
    #: honest answer to "should I expect signals for this stock?".
    scannable: bool


class StockDetailOut(StockRead):
    """The existing detail payload plus its eligibility verdict. A SUBCLASS so the list
    endpoint's `StockRead` is untouched — a list has no business paying for a bar count."""

    eligibility: StockEligibilityOut | None = None
