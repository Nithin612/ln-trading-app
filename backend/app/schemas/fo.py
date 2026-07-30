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
