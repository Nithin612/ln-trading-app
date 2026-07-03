"""Pydantic schemas for Phase 11 — External Portfolio."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

MANUAL_ASSET_TYPES = frozenset({"gold", "fd", "ppf", "nps", "bonds", "real_estate", "other"})


# ── Manual Asset schemas ───────────────────────────────────────────────────────

class ManualAssetCreate(BaseModel):
    asset_type: str
    name: str
    institution: str | None = None
    current_value: Decimal
    purchase_value: Decimal | None = None
    purchase_date: date | None = None
    maturity_date: date | None = None
    units: Decimal | None = None
    unit_price: Decimal | None = None
    notes: str | None = None

    @field_validator("asset_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in MANUAL_ASSET_TYPES:
            raise ValueError(f"asset_type must be one of {sorted(MANUAL_ASSET_TYPES)}")
        return v

    @field_validator("current_value")
    @classmethod
    def validate_value(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("current_value must be non-negative")
        return v


class ManualAssetUpdate(BaseModel):
    asset_type: str | None = None
    name: str | None = None
    institution: str | None = None
    current_value: Decimal | None = None
    purchase_value: Decimal | None = None
    purchase_date: date | None = None
    maturity_date: date | None = None
    units: Decimal | None = None
    unit_price: Decimal | None = None
    notes: str | None = None

    @field_validator("asset_type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in MANUAL_ASSET_TYPES:
            raise ValueError(f"asset_type must be one of {sorted(MANUAL_ASSET_TYPES)}")
        return v

    @field_validator("current_value")
    @classmethod
    def validate_value(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("current_value must be non-negative")
        return v


class ManualAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    asset_type: str
    name: str
    institution: str | None
    current_value: Decimal
    purchase_value: Decimal | None
    purchase_date: date | None
    maturity_date: date | None
    units: Decimal | None
    unit_price: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ── MF Holding / Batch schemas ─────────────────────────────────────────────────

class MfHoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    user_id: int
    amc_name: str
    scheme_name: str
    folio_number: str
    isin: str | None
    units: Decimal
    nav: Decimal
    current_value: Decimal
    as_of_date: date | None
    created_at: datetime


class MfImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    statement_date: date | None
    investor_name: str | None
    pan: str | None
    source_filename: str
    total_holdings: int
    total_value: Decimal
    created_at: datetime


class MfImportBatchDetail(MfImportBatchOut):
    holdings: list[MfHoldingOut] = []


# ── Net-worth schemas ──────────────────────────────────────────────────────────

class AssetBreakdownItem(BaseModel):
    asset_type: str
    label: str
    total_value: Decimal
    count: int


class EquitySummary(BaseModel):
    current_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    position_count: int


class MfSummary(BaseModel):
    current_value: Decimal
    holding_count: int
    last_imported: datetime | None


class ManualSummary(BaseModel):
    current_value: Decimal
    count: int
    breakdown: list[AssetBreakdownItem]


class NetWorthOut(BaseModel):
    equity: EquitySummary
    mutual_funds: MfSummary
    manual_assets: ManualSummary
    total_net_worth: Decimal
    as_of: datetime
