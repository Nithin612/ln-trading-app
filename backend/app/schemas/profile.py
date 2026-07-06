"""Typed shapes for strategy-profile JSONB columns (Phase 2 slice 4).

A profile can only PARAMETERIZE registered code paths, never introduce
behavior — unknown kinds/types are rejected at load (reject-don't-clamp).
`config_hash` is the drift guard: goldens pin it, and CI fails when a
profile's config changes without a version bump.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

# The six weight groups of the existing preset system (backtest/grid_search).
VALID_WEIGHT_GROUPS = {"pattern", "trend", "momentum", "volume", "structure", "institutional"}

# Setup types the app/profiles registry implements (slice 5). A slice-5 test
# asserts registry keys == this set, so the two can never drift silently.
KNOWN_SETUP_TYPES = {
    "pdh_breakout",
    "pdl_breakdown",
    "opening_gap",
    "relative_strength",
    "dc1",
    "dc2",
    "orb_breakout",
    "top_gainer_925",
    "factor_score",
}

PROFILE_STYLES = ("intraday", "swing", "fno", "investment")
PROFILE_SCHEDULES = ("eod", "intraday_15m", "intraday_5m", "time_0925")


def _require_decimal(v: str, *, positive: bool = True) -> str:
    try:
        d = Decimal(v)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"not a Decimal string: {v!r}") from exc
    if positive and d <= 0:
        raise ValueError(f"must be > 0: {v!r}")
    return v


# ── universe_spec ────────────────────────────────────────────────────────────


class IndexUniverse(BaseModel):
    kind: Literal["index"]
    value: Literal["NIFTY50", "BANKNIFTY"]


class FlagUniverse(BaseModel):
    kind: Literal["flag"]
    value: Literal["fno"]


class AllActiveUniverse(BaseModel):
    kind: Literal["all_active"]


class SymbolsUniverse(BaseModel):
    kind: Literal["symbols"]
    value: list[str] = Field(min_length=1)


class CategoryUniverse(BaseModel):
    kind: Literal["category"]
    value: str = Field(min_length=1)  # category slug


UniverseSpec = Annotated[
    IndexUniverse | FlagUniverse | AllActiveUniverse | SymbolsUniverse | CategoryUniverse,
    Field(discriminator="kind"),
]


# ── setup_conditions ─────────────────────────────────────────────────────────


class SetupConditionSpec(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in KNOWN_SETUP_TYPES:
            raise ValueError(f"unknown setup type {v!r} — not in the registry")
        return v


# ── risk_template (§6 TP policies; SL stays classification canon) ────────────


class RrTemplate(BaseModel):
    kind: Literal["rr"]
    ratio: str  # Decimal string, e.g. "1.5", "2"

    @field_validator("ratio")
    @classmethod
    def _dec(cls, v: str) -> str:
        return _require_decimal(v)


class FlatPctTemplate(BaseModel):
    kind: Literal["flat_pct"]
    target_pct: str

    @field_validator("target_pct")
    @classmethod
    def _dec(cls, v: str) -> str:
        return _require_decimal(v)


class FlatPctTrailingTemplate(BaseModel):
    kind: Literal["flat_pct_trailing"]
    target_pct: str
    book_fraction: str = "0.5"

    @field_validator("target_pct", "book_fraction")
    @classmethod
    def _dec(cls, v: str) -> str:
        return _require_decimal(v)


class EmaTrailTemplate(BaseModel):
    kind: Literal["ema_trail"]
    min_target_pct: str
    ema_length: int = Field(default=20, ge=2, le=200)
    ema_timeframe: Literal["1d"] = "1d"

    @field_validator("min_target_pct")
    @classmethod
    def _dec(cls, v: str) -> str:
        return _require_decimal(v)


RiskTemplate = Annotated[
    RrTemplate | FlatPctTemplate | FlatPctTrailingTemplate | EmaTrailTemplate,
    Field(discriminator="kind"),
]


# ── validity_spec ────────────────────────────────────────────────────────────


class TradingDaysValidity(BaseModel):
    kind: Literal["trading_days"]
    n: int = Field(ge=1, le=60)


class SameDayValidity(BaseModel):
    kind: Literal["same_day"]
    cutoff: str = "15:15"  # IST wall clock


ValiditySpec = Annotated[
    TradingDaysValidity | SameDayValidity, Field(discriminator="kind")
]


# ── the full config (hash source) ────────────────────────────────────────────


class StrategyProfileConfig(BaseModel):
    """Everything that defines a profile version's behavior. This is the
    canonical hash source — DB rows store these fields verbatim."""

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    style: Literal["intraday", "swing", "fno", "investment"]
    timeframe: Literal["1d", "1h", "15m", "5m", "1m"]
    schedule: Literal["eod", "intraday_15m", "intraday_5m", "time_0925"]
    universe_spec: UniverseSpec
    setup_conditions: list[SetupConditionSpec] = Field(default_factory=list)
    weight_multipliers: dict[str, float] = Field(default_factory=dict)
    min_confidence: int = Field(default=70, ge=70, le=100)
    risk_template: RiskTemplate
    validity_spec: ValiditySpec | None = None

    @field_validator("weight_multipliers")
    @classmethod
    def _groups_and_bounds(cls, v: dict[str, float]) -> dict[str, float]:
        unknown = set(v) - VALID_WEIGHT_GROUPS
        if unknown:
            raise ValueError(f"unknown weight groups: {sorted(unknown)}")
        for group, mult in v.items():
            if not (0 < mult <= 3):
                raise ValueError(f"multiplier for {group} out of (0, 3]: {mult}")
        return v


def compute_config_hash(config: StrategyProfileConfig) -> str:
    """sha256 of the canonical JSON — key-order independent."""
    canonical = json.dumps(
        config.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
