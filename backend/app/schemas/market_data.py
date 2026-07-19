from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field  # noqa: I001

# ── OHLCV ─────────────────────────────────────────────────────────────────────

class OhlcvBar(BaseModel):
    """Single daily OHLCV bar — used by the candlestick chart."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OhlcvResponse(BaseModel):
    stock_id: int
    timeframe: str = "1d"
    bars: list[OhlcvBar]


# ── FII / DII ─────────────────────────────────────────────────────────────────

class FiiDiiRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    investor_type: str
    segment: str
    buy_value_cr: Decimal
    sell_value_cr: Decimal
    net_value_cr: Decimal  # computed on read: buy - sell


class FiiDiiResponse(BaseModel):
    rows: list[FiiDiiRow]
    total: int


# ── Bulk / Block deals ────────────────────────────────────────────────────────

class BulkBlockDealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_date: date
    stock_id: int
    symbol: str | None = None
    deal_type: str
    client_name: str | None
    transaction: str
    quantity: int
    price: Decimal
    value_cr: Decimal
    source: str


class BulkBlockDealsResponse(BaseModel):
    items: list[BulkBlockDealRead]
    total: int


# ── Ingestion trigger ─────────────────────────────────────────────────────────

class IngestionResult(BaseModel):
    status: str
    date: date
    rows_inserted: int
    rows_skipped: int
    message: str = ""


class BackfillRequest(BaseModel):
    from_date: date = Field(description="Start date for backfill (inclusive)")
    to_date: date = Field(description="End date for backfill (inclusive)")


# ── Provisional leaderboards (Phase 3, slice 3.5-deferred) ────────────────────
# Derived observability view — provisional-labelled end-to-end, never
# tradeable state. Confidence None = active-signal pair now below its gate.

class ProvisionalRow(BaseModel):
    provisional: bool = True
    stock_id: int
    symbol: str
    profile_key: str | None
    style: str
    tf: str
    confidence: int | None
    direction: str | None
    # True = passes the gate · False = a real below-gate verdict ·
    # None = window unusable (no data) — the score says nothing.
    gate: bool | None
    sources: list[str]
    signal_id: str | None = None


class ProvisionalLeaderboardOut(BaseModel):
    provisional: bool = True
    style: str
    as_of: datetime | None = None
    rows: list[ProvisionalRow] = []
