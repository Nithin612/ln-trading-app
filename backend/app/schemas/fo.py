"""F&O analytics API schemas — Phase 4 slice 4.1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class UnderlyingsOut(BaseModel):
    """F&O underlyings with option rows on the latest recorded day."""

    as_of: date | None
    symbols: list[str]


class ExpiryOut(BaseModel):
    expiry: date
    dte: int                  # calendar days from the chain's day to expiry


class ExpiriesOut(BaseModel):
    symbol: str
    as_of: date | None        # the recorded day these expiries are open on
    expiries: list[ExpiryOut]


class ChainLegOut(BaseModel):
    strike: Decimal
    option_type: str          # CE | PE
    oi: int
    volume: int
    ltp: Decimal | None
    # Populated only when ?greeks=true AND the quote inverts. None means
    # "not priced" — never zero, which would read as a real value on screen.
    iv: float | None = None           # annualized, Black-76 on the future
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None         # per 1.00 of IV (100 vol points)
    theta: float | None = None        # per year


class ChainOut(BaseModel):
    symbol: str
    expiry: date
    source: str               # eod | intraday
    spot: Decimal | None
    atm_strike: Decimal | None
    legs: list[ChainLegOut]
    # What the Greeks were priced off (null unless ?greeks=true resolved them).
    # Stated explicitly so the UI can never imply live Greeks off a stale chain.
    as_of: date | None = None         # the chain's own trading day
    fut_price: Decimal | None = None  # Black-76 forward
    dte: int | None = None            # calendar days from as_of to expiry


class PcrOut(BaseModel):
    pcr_oi: float | None
    pcr_volume: float | None
    total_ce_oi: int
    total_pe_oi: int


class BasisOut(BaseModel):
    fut_close: Decimal
    underlying_close: Decimal
    basis: Decimal
    basis_pct: float


class VixRegimeOut(BaseModel):
    current: Decimal
    percentile: float
    band: str                 # low | normal | high
    sample: int


class IvRankOut(BaseModel):
    symbol: str
    as_of: date
    current_iv: float
    rank: float
    percentile: float
    min_iv: float
    max_iv: float
    sample: int


class OptionLegOut(BaseModel):
    action: str          # sell | buy
    option_type: str     # CE | PE
    strike: Decimal
    premium: Decimal


class ExitPlanOut(BaseModel):
    take_profit_credit: Decimal
    stop_loss_amount: Decimal
    time_stop_dte: int


class SuggestionOut(BaseModel):
    structure: str       # bull_put | bear_call | iron_condor
    legs: list[OptionLegOut]
    net_credit: Decimal
    max_profit: Decimal
    max_loss: Decimal
    width: Decimal
    breakevens: list[Decimal]
    pop: float
    expectancy: Decimal
    margin_est: Decimal
    return_on_margin: float
    short_delta: float
    dte: int
    expiry: date
    exit_plan: ExitPlanOut
    rationale: str


class SuggestionsOut(BaseModel):
    symbol: str
    candidates: list[SuggestionOut]


class FoAnalyticsOut(BaseModel):
    symbol: str
    expiry: date
    source: str
    spot: Decimal | None
    atm_strike: Decimal | None
    pcr: PcrOut
    max_pain: Decimal | None
    basis: BasisOut | None
    vix: VixRegimeOut | None
