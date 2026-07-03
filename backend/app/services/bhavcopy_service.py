"""
NSE bhavcopy downloader, parser, and upsert service.

NSE publishes two useful bhavcopy formats:
  1. Full bhavcopy (sec_bhavdata_full): contains EQ-series OHLCV for all CM stocks.
     URL: https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
  2. Compact bhav (cm<DD><MMM><YYYY>bhav.csv): older archives, still available via zip.

We primarily use format #1.  Columns of interest (after strip/lower):
  SYMBOL, SERIES, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE,
  TTL_TRD_QNTY, DATE1

On insert we do ON CONFLICT (time, stock_id) DO NOTHING so re-running on the
same date is always safe.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import IO

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.market_data import IngestionResult

log = logging.getLogger(__name__)

# NSE requires a browser-like User-Agent to avoid 403 responses.
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

_BHAV_URL_PATTERN = (
    "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date}.csv"
)


@dataclass
class BhavRow:
    """Parsed and validated row from the bhavcopy CSV."""

    symbol: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def _parse_decimal(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned in ("-", "0.00"):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_int(raw: str) -> int | None:
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned == "-":
        return None
    try:
        return int(float(cleaned))
    except (ValueError, OverflowError):
        return None


def _normalise_headers(headers: list[str]) -> list[str]:
    return [h.strip().upper().replace(" ", "_") for h in headers]


def parse_bhavcopy_csv(fileobj: IO[str]) -> list[BhavRow]:
    """
    Parse a bhavcopy CSV stream and return validated BhavRow records.

    Only EQ (equity) series rows are kept; rows with missing price data are dropped.
    The DATE1 column is used for the trade date (format: DD-MMM-YYYY or DD-Mon-YYYY).
    """
    reader = csv.DictReader(fileobj)
    if reader.fieldnames is None:
        return []

    norm = {_normalise_headers([f])[0]: f for f in reader.fieldnames}

    def col(key: str) -> str:
        return norm.get(key, key)

    rows: list[BhavRow] = []
    for raw in reader:
        series = raw.get(col("SERIES"), "").strip().upper()
        if series != "EQ":
            continue

        symbol = raw.get(col("SYMBOL"), "").strip().upper()
        if not symbol:
            continue

        open_v = _parse_decimal(raw.get(col("OPEN_PRICE"), ""))
        high_v = _parse_decimal(raw.get(col("HIGH_PRICE"), ""))
        low_v = _parse_decimal(raw.get(col("LOW_PRICE"), ""))
        close_v = _parse_decimal(raw.get(col("CLOSE_PRICE"), ""))
        volume_v = _parse_int(raw.get(col("TTL_TRD_QNTY"), ""))

        if None in (open_v, high_v, low_v, close_v, volume_v):
            log.debug("Skipping %s — missing price/volume data", symbol)
            continue

        date_raw = raw.get(col("DATE1"), "").strip()
        try:
            trade_date = datetime.strptime(date_raw, "%d-%b-%Y").date()
        except ValueError:
            try:
                trade_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                log.warning("Cannot parse date %r for %s — skipping", date_raw, symbol)
                continue

        rows.append(
            BhavRow(
                symbol=symbol,
                trade_date=trade_date,
                open=open_v,  # type: ignore[arg-type]
                high=high_v,  # type: ignore[arg-type]
                low=low_v,  # type: ignore[arg-type]
                close=close_v,  # type: ignore[arg-type]
                volume=volume_v,  # type: ignore[arg-type]
            )
        )

    return rows


async def download_bhavcopy(trade_date: date) -> str | None:
    """
    Download the NSE bhavcopy CSV for *trade_date* and return its text content.

    Returns None if NSE returns a non-200 status (e.g., market holiday / weekend).
    """
    date_str = trade_date.strftime("%d%m%Y")
    url = _BHAV_URL_PATTERN.format(date=date_str)

    async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=30, follow_redirects=True) as c:
        # NSE requires a prior visit to nseindia.com to set cookies.
        try:
            await c.get("https://www.nseindia.com/", timeout=10)
        except httpx.HTTPError:
            pass  # best-effort cookie priming

        resp = await c.get(url)

    if resp.status_code != 200:
        log.info("Bhavcopy not available for %s (HTTP %s)", trade_date, resp.status_code)
        return None

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        log.info("Bhavcopy returned HTML (likely blocked) for %s", trade_date)
        return None

    return resp.text


async def upsert_bhavcopy_rows(
    db: AsyncSession,
    rows: list[BhavRow],
) -> tuple[int, int]:
    """
    Upsert parsed BhavRow records into ohlcv_1d.

    Returns (inserted, skipped).
    Skips symbols not present in the stocks table.
    Uses ON CONFLICT DO NOTHING so re-running is always idempotent.
    """
    if not rows:
        return 0, 0

    # Build a symbol → stock_id map for all symbols we need.
    symbols = list({r.symbol for r in rows})
    result = await db.execute(
        text(
            "SELECT symbol, id FROM stocks "
            "WHERE symbol = ANY(:syms) AND exchange = 'NSE' AND is_active = true"
        ),
        {"syms": symbols},
    )
    sym_to_id: dict[str, int] = {row.symbol: row.id for row in result}

    inserted = 0
    skipped = 0

    for row in rows:
        stock_id = sym_to_id.get(row.symbol)
        if stock_id is None:
            skipped += 1
            continue

        # Store as UTC midnight of the trade date.
        candle_time = datetime(
            row.trade_date.year, row.trade_date.month, row.trade_date.day, tzinfo=UTC
        )

        result = await db.execute(
            text(
                "INSERT INTO ohlcv_1d"
                " (time, stock_id, open, high, low, close, volume, is_complete)"
                " VALUES (:t, :sid, :o, :h, :l, :c, :v, true)"
                " ON CONFLICT (time, stock_id) DO NOTHING"
                " RETURNING time"
            ),
            {
                "t": candle_time,
                "sid": stock_id,
                "o": row.open,
                "h": row.high,
                "l": row.low,
                "c": row.close,
                "v": row.volume,
            },
        )
        if result.fetchone():
            inserted += 1
        else:
            skipped += 1

    await db.commit()
    return inserted, skipped


async def ingest_bhavcopy_date(
    db: AsyncSession,
    trade_date: date,
    csv_text: str | None = None,
) -> IngestionResult:
    """
    Download (if csv_text is None) and ingest bhavcopy for a single trade date.

    Pass csv_text to skip the download step (useful for tests and manual imports).
    """
    if csv_text is None:
        csv_text = await download_bhavcopy(trade_date)

    if csv_text is None:
        return IngestionResult(
            status="skipped",
            date=trade_date,
            rows_inserted=0,
            rows_skipped=0,
            message="Bhavcopy not available (holiday or weekend)",
        )

    rows = parse_bhavcopy_csv(io.StringIO(csv_text))

    if not rows:
        return IngestionResult(
            status="skipped",
            date=trade_date,
            rows_inserted=0,
            rows_skipped=0,
            message="CSV parsed but contained no valid EQ rows",
        )

    inserted, skipped = await upsert_bhavcopy_rows(db, rows)

    log.info(
        "Bhavcopy %s: %d inserted, %d skipped (unknown symbol)",
        trade_date, inserted, skipped,
    )
    return IngestionResult(
        status="ok",
        date=trade_date,
        rows_inserted=inserted,
        rows_skipped=skipped,
    )
