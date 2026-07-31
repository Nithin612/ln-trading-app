"""F&O analytics API schemas — Phase 4 slice 4.1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ChainLegOut(BaseModel):
    strike: Decimal
    option_type: str          # CE | PE
    oi: int
    volume: int
    ltp: Decimal | None


class ChainOut(BaseModel):
    symbol: str
    expiry: date
    source: str               # eod | intraday
    spot: Decimal | None
    atm_strike: Decimal | None
    legs: list[ChainLegOut]


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


class SuggestionOut(BaseModel):
    structure: str       # bull_put | bear_call | iron_condor
    legs: list[OptionLegOut]
    net_credit: Decimal
    max_profit: Decimal
    max_loss: Decimal
    width: Decimal
    breakevens: list[Decimal]
    pop: float
    margin_est: Decimal
    return_on_margin: float
    short_delta: float
    dte: int
    expiry: date
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
