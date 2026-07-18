"""
FII/DII institutional flow fetcher and bulk/block deal ingestion.

Sources:
  - FII/DII: NSE API  https://www.nseindia.com/api/fiidiiTradeReact
    Serves ONLY the latest trading day (verified 2026-07-18), as flat
    cash aggregates; the segmented cash+F&O shape is legacy but still
    parsed if NSE ever reverts.
  - Bulk deals (NSE): https://www.nseindia.com/api/snapshot-capital-market-wholesaleDebt-reports
    or the downloadable CSV from NSE's bulk deal page.
  - Block deals (NSE): similar NSE API endpoint.

All dates stored as trade_date (DATE), INR values in crores.
ON CONFLICT DO NOTHING makes all inserts idempotent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

_FIIDII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
_BULK_DEALS_URL = "https://www.nseindia.com/api/snapshot-capital-market-wholesaleDebt-reports"


@dataclass
class FiiDiiRecord:
    trade_date: date
    investor_type: str  # 'FII' | 'DII'
    segment: str  # 'cash' | 'futures' | 'options'
    buy_value_cr: Decimal
    sell_value_cr: Decimal


@dataclass
class BulkDealRecord:
    trade_date: date
    symbol: str
    deal_type: str  # 'bulk' | 'block'
    client_name: str | None
    transaction: str  # 'BUY' | 'SELL'
    quantity: int
    price: Decimal
    source: str  # 'NSE' | 'BSE'


def _to_decimal(val: object) -> Decimal | None:
    if val is None:
        return None
    try:
        cleaned = str(val).replace(",", "").strip()
        if not cleaned or cleaned == "-":
            return None
        d = Decimal(cleaned)
        # "NaN"/"Infinity" parse as valid Decimals AND fit Numeric columns —
        # one such row would poison every SUM() rollup downstream (§2.7).
        return d if d.is_finite() else None
    except InvalidOperation:
        return None


def _to_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, OverflowError):
        return None


def _parse_nse_date(raw: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_fii_dii_response(payload: list[dict[str, object]]) -> list[FiiDiiRecord]:
    """
    Parse the NSE fiidiiTradeReact JSON response into FiiDiiRecord list.

    Handles BOTH shapes NSE has served (2026-07-18 incident: the live API
    returned the flat shape, the parser only knew the segmented one, so
    every fetch parsed to ZERO records and fii_dii_daily stayed empty):

    Flat cash aggregate (the live shape as of 2026-07):
      {"date": "17-Jul-2026", "category": "DII",
       "buyValue": "17180.08", "sellValue": "16162.19", "netValue": "1017.89"}

    Segmented (legacy):
      {"date": "18-May-2026", "category": "FII/FPI *",
       "buyCF": "12345.67", "sellCF": "9876.54", "netCF": "2469.13",
       ...buyFF, sellFF, netFF, buyOF, sellOF, netOF (F&O breakdown)}

    buyValue/sellValue are the cash-market aggregates — the segment
    get_market_flow_5d consumes for SIGNAL_ENGINE.md §2.7.
    """
    records: list[FiiDiiRecord] = []

    for item in payload:
        raw_date = item.get("date", "")
        trade_date = _parse_nse_date(str(raw_date))
        if trade_date is None:
            log.warning("FII/DII: cannot parse date %r — skipping row", raw_date)
            continue

        category_raw = str(item.get("category", "")).upper()
        if "FII" in category_raw or "FPI" in category_raw:
            investor_type = "FII"
        elif "DII" in category_raw:
            investor_type = "DII"
        else:
            log.debug("FII/DII: unknown category %r — skipping", category_raw)
            continue

        # Cash: segmented buyCF/sellCF wins when present — in a payload
        # carrying both shapes, buyValue is plausibly a TOTAL (cash+F&O)
        # and must not be recorded as the cash segment. Flat-only rows
        # (the live 2026-07 shape) fall back to buyValue/sellValue.
        buy_cf = _to_decimal(item.get("buyCF"))
        sell_cf = _to_decimal(item.get("sellCF"))
        if buy_cf is None and sell_cf is None:
            buy_flat = _to_decimal(item.get("buyValue"))
            sell_flat = _to_decimal(item.get("sellValue"))
            if buy_flat is not None and sell_flat is not None:
                records.append(
                    FiiDiiRecord(
                        trade_date=trade_date,
                        investor_type=investor_type,
                        segment="cash",
                        buy_value_cr=buy_flat,
                        sell_value_cr=sell_flat,
                    )
                )
        if buy_cf is not None and sell_cf is not None:
            records.append(
                FiiDiiRecord(
                    trade_date=trade_date,
                    investor_type=investor_type,
                    segment="cash",
                    buy_value_cr=buy_cf,
                    sell_value_cr=sell_cf,
                )
            )

        # Futures segment
        buy_ff = _to_decimal(item.get("buyFF"))
        sell_ff = _to_decimal(item.get("sellFF"))
        if buy_ff is not None and sell_ff is not None:
            records.append(
                FiiDiiRecord(
                    trade_date=trade_date,
                    investor_type=investor_type,
                    segment="futures",
                    buy_value_cr=buy_ff,
                    sell_value_cr=sell_ff,
                )
            )

        # Options segment
        buy_of = _to_decimal(item.get("buyOF"))
        sell_of = _to_decimal(item.get("sellOF"))
        if buy_of is not None and sell_of is not None:
            records.append(
                FiiDiiRecord(
                    trade_date=trade_date,
                    investor_type=investor_type,
                    segment="options",
                    buy_value_cr=buy_of,
                    sell_value_cr=sell_of,
                )
            )

    return records


async def _prime_nse_session(client: httpx.AsyncClient) -> None:
    """Visit NSE home to acquire session cookie before API calls."""
    try:
        await client.get("https://www.nseindia.com/", timeout=10)
    except httpx.HTTPError:
        pass


async def fetch_fii_dii_data() -> list[FiiDiiRecord]:
    """Download and parse FII/DII data from NSE.

    The live endpoint serves only the LATEST trading day (verified
    2026-07-18 — the old "~30 trading days" claim was wrong), so flows
    are capture-as-you-go: a day the worker misses entirely is gone from
    this source. The 5-day rollup treats missing days as zero by design.
    """
    async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=30, follow_redirects=True) as c:
        await _prime_nse_session(c)
        resp = await c.get(_FIIDII_URL)

    if resp.status_code != 200:
        log.warning("FII/DII API returned %s", resp.status_code)
        return []

    try:
        payload = resp.json()
    except Exception:
        log.warning("FII/DII API returned non-JSON response")
        return []

    return parse_fii_dii_response(payload if isinstance(payload, list) else [])


async def upsert_fii_dii(
    db: AsyncSession,
    records: list[FiiDiiRecord],
) -> tuple[int, int]:
    """Insert FiiDiiRecord list into fii_dii_daily.  Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for rec in records:
        result = await db.execute(
            text(
                "INSERT INTO fii_dii_daily "
                "(trade_date, investor_type, segment, buy_value_cr, sell_value_cr) "
                "VALUES (:d, :it, :seg, :buy, :sell) "
                "ON CONFLICT (trade_date, investor_type, segment) DO NOTHING "
                "RETURNING trade_date"
            ),
            {
                "d": rec.trade_date,
                "it": rec.investor_type,
                "seg": rec.segment,
                "buy": rec.buy_value_cr,
                "sell": rec.sell_value_cr,
            },
        )
        if result.fetchone():
            inserted += 1
        else:
            skipped += 1

    await db.commit()
    return inserted, skipped


def parse_bulk_deals_response(
    payload: list[dict[str, object]], deal_type: str
) -> list[BulkDealRecord]:
    """
    Parse NSE bulk or block deal JSON response.

    Expected fields per item: BD_DT_DATE, BD_SYMBOL, BD_CLIENT_NAME,
    BD_BUY_SELL, BD_QTY_TRD, BD_TP_WATP
    """
    records: list[BulkDealRecord] = []

    for item in payload:
        raw_date = str(item.get("BD_DT_DATE", ""))
        trade_date = _parse_nse_date(raw_date)
        if trade_date is None:
            continue

        symbol = str(item.get("BD_SYMBOL", "")).strip().upper()
        if not symbol:
            continue

        txn_raw = str(item.get("BD_BUY_SELL", "")).strip().upper()
        txn = "BUY" if txn_raw.startswith("B") else "SELL" if txn_raw.startswith("S") else None
        if txn is None:
            continue

        qty = _to_int(item.get("BD_QTY_TRD"))
        price = _to_decimal(item.get("BD_TP_WATP"))
        if qty is None or price is None:
            continue

        records.append(
            BulkDealRecord(
                trade_date=trade_date,
                symbol=symbol,
                deal_type=deal_type,
                client_name=str(item.get("BD_CLIENT_NAME", "")).strip() or None,
                transaction=txn,
                quantity=qty,
                price=price,
                source="NSE",
            )
        )

    return records


async def upsert_bulk_deals(
    db: AsyncSession,
    records: list[BulkDealRecord],
) -> tuple[int, int]:
    """Insert bulk/block deal records.  Returns (inserted, skipped)."""
    if not records:
        return 0, 0

    symbols = list({r.symbol for r in records})
    sym_result = await db.execute(
        text("SELECT symbol, id FROM stocks WHERE symbol = ANY(:s) AND exchange = 'NSE'"),
        {"s": symbols},
    )
    sym_to_id: dict[str, int] = {row.symbol: row.id for row in sym_result}

    inserted = 0
    skipped = 0

    for rec in records:
        stock_id = sym_to_id.get(rec.symbol)
        if stock_id is None:
            skipped += 1
            continue

        result = await db.execute(
            text(
                "INSERT INTO bulk_block_deals "
                "(trade_date, stock_id, deal_type, client_name, transaction,"
                " quantity, price, source) "
                "VALUES (:d, :sid, :dt, :cn, :txn, :qty, :price, :src) "
                "ON CONFLICT (trade_date, stock_id, deal_type, client_name,"
                " transaction, quantity, price, source) DO NOTHING "
                "RETURNING id"
            ),
            {
                "d": rec.trade_date,
                "sid": stock_id,
                "dt": rec.deal_type,
                "cn": rec.client_name,
                "txn": rec.transaction,
                "qty": rec.quantity,
                "price": rec.price,
                "src": rec.source,
            },
        )
        if result.fetchone():
            inserted += 1
        else:
            skipped += 1

    await db.commit()
    return inserted, skipped


# ── §2.7 flow rollups for signal generation (Phase 2 slice 3) ────────────────


async def get_market_flow_5d(db: AsyncSession, as_of: date) -> tuple[Decimal, Decimal]:
    """(fii_net_5d, dii_net_5d): cumulative net CASH-segment flow in ₹ crore
    over the last 5 NSE trading days ending at `as_of`.

    SIGNAL_ENGINE.md §2.7 measures "last 5 trading days, aggregated" — the
    cash segment is the institutional-conviction measure (futures/options
    legs are hedging-dominated and excluded).
    """
    from app.services.market_calendar import last_n_trading_days

    days = await last_n_trading_days(db, as_of, 5)
    rows = (
        await db.execute(
            text(
                "SELECT investor_type,"
                " COALESCE(SUM(buy_value_cr - sell_value_cr), 0) AS net"
                " FROM fii_dii_daily"
                " WHERE trade_date = ANY(:days) AND segment = 'cash'"
                " GROUP BY investor_type"
            ),
            {"days": days},
        )
    ).all()
    nets = {r.investor_type: Decimal(r.net) for r in rows}
    return nets.get("FII", Decimal("0")), nets.get("DII", Decimal("0"))


async def get_stock_block_deal_net_cr(db: AsyncSession, stock_id: int, as_of: date) -> Decimal:
    """Net bulk/block-deal value in ₹ crore for one stock over the last 5
    NSE trading days ending at `as_of` (BUY positive, SELL negative)."""
    from app.services.market_calendar import last_n_trading_days

    days = await last_n_trading_days(db, as_of, 5)
    row = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM("
                " CASE WHEN transaction = 'BUY' THEN quantity * price"
                "      ELSE -(quantity * price) END), 0) AS net"
                " FROM bulk_block_deals"
                " WHERE stock_id = :sid AND trade_date = ANY(:days)"
            ),
            {"sid": stock_id, "days": days},
        )
    ).one()
    return (Decimal(row.net) / Decimal(10**7)).quantize(Decimal("0.01"))
