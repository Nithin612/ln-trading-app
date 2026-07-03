"""
Screener field catalog — the authoritative whitelist of filterable fields.

Each entry maps a public field name (used in the API) to a SQLAlchemy column
on the Stock model and the set of operators that make sense for that type.

Phase 2 covers stocks-table columns only.  Indicator/FII/pattern filters
arrive in Phase 4+ once their underlying data exists.  Fields listed as
`available=False` are shown in the UI as "coming soon" but rejected server-side
with a clear error message rather than a silent empty result.
"""
from dataclasses import dataclass
from typing import Any, Literal

from app.models.stock import Stock

FieldType = Literal["bool", "str", "int", "decimal", "date"]
OpSet = frozenset[str]

BOOL_OPS: OpSet = frozenset({"eq"})
STR_OPS: OpSet = frozenset({"eq", "neq", "like", "in"})
NUM_OPS: OpSet = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "between"})
DATE_OPS: OpSet = frozenset({"eq", "gt", "gte", "lt", "lte", "between"})


@dataclass(frozen=True)
class FieldDef:
    column: Any
    field_type: FieldType
    allowed_ops: OpSet
    available: bool = True
    note: str = ""


# Keyed by the public field name clients send in filter specs.
CATALOG: dict[str, FieldDef] = {
    # ── Boolean flags ────────────────────────────────────────────────
    "is_nifty50": FieldDef(
        column=Stock.is_nifty50,
        field_type="bool",
        allowed_ops=BOOL_OPS,
    ),
    "is_banknifty": FieldDef(
        column=Stock.is_banknifty,
        field_type="bool",
        allowed_ops=BOOL_OPS,
    ),
    "is_finnifty": FieldDef(
        column=Stock.is_finnifty,
        field_type="bool",
        allowed_ops=BOOL_OPS,
    ),
    "is_fno": FieldDef(
        column=Stock.is_fno,
        field_type="bool",
        allowed_ops=BOOL_OPS,
    ),
    "is_active": FieldDef(
        column=Stock.is_active,
        field_type="bool",
        allowed_ops=BOOL_OPS,
    ),
    # ── String fields ────────────────────────────────────────────────
    "symbol": FieldDef(
        column=Stock.symbol,
        field_type="str",
        allowed_ops=STR_OPS,
    ),
    "exchange": FieldDef(
        column=Stock.exchange,
        field_type="str",
        allowed_ops=STR_OPS,
    ),
    "sector": FieldDef(
        column=Stock.sector,
        field_type="str",
        allowed_ops=STR_OPS,
    ),
    "industry": FieldDef(
        column=Stock.industry,
        field_type="str",
        allowed_ops=STR_OPS,
    ),
    "isin": FieldDef(
        column=Stock.isin,
        field_type="str",
        allowed_ops=STR_OPS,
    ),
    # ── Numeric fields ───────────────────────────────────────────────
    "lot_size": FieldDef(
        column=Stock.lot_size,
        field_type="int",
        allowed_ops=NUM_OPS,
    ),
    "market_cap_cr": FieldDef(
        column=Stock.market_cap_cr,
        field_type="decimal",
        allowed_ops=NUM_OPS,
        note="Populated in Phase 4. Filters on this field return no results until then.",
    ),
    # ── Date fields ──────────────────────────────────────────────────
    "listed_on": FieldDef(
        column=Stock.listed_on,
        field_type="date",
        allowed_ops=DATE_OPS,
    ),
    # ── Phase 4+ fields (not yet available) ─────────────────────────
    "indicator.rsi_14": FieldDef(
        column=Stock.id,  # placeholder — never reached because available=False
        field_type="decimal",
        allowed_ops=NUM_OPS,
        available=False,
        note="Available from Phase 4 after EOD indicator computation.",
    ),
    "indicator.price_vs_ema50": FieldDef(
        column=Stock.id,
        field_type="decimal",
        allowed_ops=NUM_OPS,
        available=False,
        note="Available from Phase 4.",
    ),
    "flow.fii_net_5d_cr": FieldDef(
        column=Stock.id,
        field_type="decimal",
        allowed_ops=NUM_OPS,
        available=False,
        note="Available from Phase 4 after FII/DII ingestion.",
    ),
}

SORT_FIELDS: dict[str, Any] = {
    "symbol": Stock.symbol,
    "company_name": Stock.company_name,
    "sector": Stock.sector,
    "market_cap_cr": Stock.market_cap_cr,
    "lot_size": Stock.lot_size,
    "listed_on": Stock.listed_on,
}
