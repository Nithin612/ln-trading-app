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


#: Real files, measured 2026-09-18: 2,059 lines (2021-06-15) · 2,628 (2024-03-01) · 3,484
#: (2026-09-17). A floor of 1,000 sits ~2x below the smallest real value.
MIN_BHAVCOPY_LINES = 1000

#: ⛔ Bodies that are not text at all, served with HTTP 200 at a `.csv` URL.
#: `PK\x03\x04` is not hypothetical: it is what NSE served for **2022-08-08**, the one
#: session the 2021-22 backfill could not ingest.
_BINARY_MAGIC: dict[bytes, str] = {
    b"PK\x03\x04": "a ZIP/XLSX workbook",
    b"\xd0\xcf\x11\xe0": "a legacy XLS workbook",
    b"%PDF": "a PDF",
    b"\x1f\x8b": "a gzip stream",
}


class BhavcopySourceError(RuntimeError):
    """NSE answered 200 with something that is not the bhavcopy we asked for.

    ⚠ Deliberately distinct from "not published" (a 404 on a holiday). Collapsing the two is
    the defect: a corrupt source reported as a holiday is a silent hole in the archive.
    """


def _assert_plausible_bhavcopy(raw: bytes, trade_date: date) -> None:
    """A10, applied to the bhavcopy — refuse a 200 OK that is not the file we asked for.

    ⛔⛔ **The magic-byte check is the one that matters, and a row-count floor would NOT have
    caught the real failure.** Measured 2026-09-18: 2022-08-08 returns HTTP 200, 233,582 bytes,
    first four bytes `PK\\x03\\x04` — a ZIP — and because ZIP payloads contain 0x0A bytes it
    counts **858 "lines"**. Any plausible line floor passes it. The two checks catch different
    failures and neither subsumes the other.

    ⚠ **This RAISES rather than returning None**, because `download_bhavcopy`'s None means
    "not published — holiday or weekend". §9.5's finding was that a ZIP whose bytes happened to
    parse as degenerate CSV would have ingested zero rows and reported success; the 2022-08-08
    failure was caught by accident, not by design.

    Mirrors `universe_materialiser._assert_plausible_equity_l` (A10) — same shape, per-source
    thresholds, deliberately not shared: the failure modes differ and the floors are measured
    against different files.
    """
    if not raw.strip():
        raise BhavcopySourceError(f"{trade_date}: EMPTY body with status 200")

    head = raw[:512]
    for magic, what in _BINARY_MAGIC.items():
        if head.startswith(magic):
            raise BhavcopySourceError(
                f"{trade_date}: served {what} at a .csv URL with status 200 "
                f"(first bytes {head[:4]!r}). This is the 2022-08-08 failure."
            )

    if head.lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise BhavcopySourceError(
            f"{trade_date}: returned HTML with status 200 — an interstitial or error page, "
            "not the CSV. Refusing to read it as an empty session."
        )

    first_line = raw.split(b"\n", 1)[0].upper()
    if b"SYMBOL" not in first_line or b"SERIES" not in first_line:
        raise BhavcopySourceError(
            f"{trade_date}: header does not name SYMBOL and SERIES — got {first_line[:120]!r}. "
            "The schema changed, or this is not a bhavcopy."
        )

    lines = raw.count(b"\n")
    if lines < MIN_BHAVCOPY_LINES:
        raise BhavcopySourceError(
            f"{trade_date}: only {lines} line(s), below the {MIN_BHAVCOPY_LINES} floor — real "
            "files carry 2,059-3,484. A truncated feed must never read as a thin session."
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


async def download_bhavcopy(
    trade_date: date, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """
    Download the NSE bhavcopy CSV for *trade_date* and return its text content.

    Returns None if NSE returns a non-200 status (e.g., market holiday / weekend).

    Pass `client` to reuse one session across many dates. A backfill walks ~950 dates and
    a fresh client each time re-primes cookies and re-handshakes TLS every single day;
    it also loses the cookie NSE sets, which is what the priming GET exists to obtain.
    """
    date_str = trade_date.strftime("%d%m%Y")
    url = _BHAV_URL_PATTERN.format(date=date_str)

    if client is not None:
        resp = await client.get(url)
    else:
        async with httpx.AsyncClient(
            headers=_NSE_HEADERS, timeout=30, follow_redirects=True
        ) as c:
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
        # ⚠ Raises now, where it used to return None. An HTML body means we were blocked or
        # redirected — a FAILURE. Returning None filed it as "holiday or weekend", which is the
        # same conflation `_assert_plausible_bhavcopy` exists to stop.
        raise BhavcopySourceError(
            f"{trade_date}: content-type {content_type!r} — HTML, not the CSV (likely blocked)"
        )

    _assert_plausible_bhavcopy(resp.content, trade_date)
    return resp.text


_CHUNK = 500


async def _ensure_historical_stocks(db: AsyncSession, symbols: list[str]) -> int:
    """Create `stocks` rows for symbols the bhavcopy names but we have never seen.

    ⭐ **This is what makes a historical backfill survivorship-safe.** Our `stocks` table
    is a TODAY snapshot built from Kite instruments, so every company that delisted,
    merged or was wound up is simply absent from it. Backtesting old data against it
    would silently drop the failures — the textbook survivorship bias, biased in exactly
    the direction that flatters results. A bhavcopy is the day's trading record and lists
    what traded THAT day, so ingesting it reconstructs the point-in-time universe.

    ⚠ Created **inactive**. These names are not tradeable today and must never enter live
    scanning, sizing or signal generation; they exist so that historical bars have
    somewhere to attach. `ON CONFLICT DO NOTHING` means an existing ACTIVE row is never
    touched — this can only add, never deactivate.

    ⚠ `company_name` is set to the symbol. The bhavcopy carries no company name, and
    inventing one would be worse than an obviously-placeholder value.
    """
    if not symbols:
        return 0
    created = 0
    for i in range(0, len(symbols), _CHUNK):
        chunk = symbols[i : i + _CHUNK]
        result = await db.execute(
            text(
                "INSERT INTO stocks (symbol, exchange, company_name, is_active)"
                " SELECT s, 'NSE', s, false FROM unnest(CAST(:syms AS varchar[])) AS s"
                " ON CONFLICT (symbol, exchange) DO NOTHING"
                " RETURNING id"
            ),
            {"syms": chunk},
        )
        created += len(result.fetchall())
    return created


async def upsert_bhavcopy_rows(
    db: AsyncSession,
    rows: list[BhavRow],
    *,
    historical: bool = False,
) -> tuple[int, int]:
    """
    Upsert parsed BhavRow records into ohlcv_1d.

    Returns (inserted, skipped).
    Uses ON CONFLICT DO NOTHING so re-running is always idempotent.

    ⭐ **D3 (2026-09-14): the price archive never consults a trading decision.**
    Both modes now attach bars to every KNOWN NSE symbol the bhavcopy names,
    active or not. The two modes differ only in whether an UNKNOWN symbol is
    CREATED (`historical=True`) or skipped — which is the honest split:
    ingestion records what traded; it does not decide which instruments exist,
    and it must not decide which are worth trading.

    ⛔ **Why this changed.** The daily path used to append ` AND is_active = true`.
    `is_active` is a *selection* flag with three writers and no owner, so a
    selection mistake silently destroyed price history: between 2026-09-07 and
    09-12 the real universe was wrongly inactive and **1,481 names lost five
    sessions of bars**. Worse, it made the repair non-durable — U3 refilled the
    hole in `historical` mode on 09-13, but `eod_catchup.py:102` calls this
    function with the default, so the very next EOD run would have written
    ~1,170 names instead of ~2,640 and **reopened the hole the next day**.

    ⚠ **On the T2T ruling (2026-07-17).** That ruling excludes `BE`/`BZ`/`SM`
    from live scanning. It is a TRADING policy, and the scanner still enforces
    it — `universe_service.resolve_universe` filters `is_active` itself. It was
    never implementable as a storage policy anyway: `parse_bhavcopy_csv` keeps
    `EQ` series only, so a name that moves to `BE` stops appearing in what we
    ingest regardless of this flag. See PART XIII of the universe plan.
    """
    if not rows:
        return 0, 0

    symbols = sorted({r.symbol for r in rows})
    if historical:
        await _ensure_historical_stocks(db, symbols)

    # D3: no tradeability predicate here, in either mode. An unknown symbol still
    # resolves to no id below and is counted as skipped — creating rows remains a
    # `historical=True` behaviour, because minting an instrument IS a universe
    # decision and this function does not make those either.
    result = await db.execute(
        text("SELECT symbol, id FROM stocks WHERE symbol = ANY(:syms) AND exchange = 'NSE'"),
        {"syms": symbols},
    )
    sym_to_id: dict[str, int] = {row.symbol: row.id for row in result}

    # One statement per chunk rather than per row: a backfill runs ~2,300 rows a day
    # across ~950 days, and a round trip each would be 2.2 million of them.
    payload: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        stock_id = sym_to_id.get(row.symbol)
        if stock_id is None:
            skipped += 1
            continue
        payload.append(
            {
                # Storage is UTC midnight of the trade date (storage UTC, market IST).
                "t": datetime(
                    row.trade_date.year, row.trade_date.month, row.trade_date.day, tzinfo=UTC
                ),
                "sid": stock_id,
                "o": row.open,
                "h": row.high,
                "l": row.low,
                "c": row.close,
                "v": row.volume,
            }
        )

    inserted = 0
    for i in range(0, len(payload), _CHUNK):
        chunk = payload[i : i + _CHUNK]
        values = ", ".join(
            f"(:t{j}, :sid{j}, :o{j}, :h{j}, :l{j}, :c{j}, :v{j}, true)"
            for j in range(len(chunk))
        )
        params: dict[str, object] = {}
        for j, item in enumerate(chunk):
            for k, v in item.items():
                params[f"{k}{j}"] = v
        result = await db.execute(
            text(
                "INSERT INTO ohlcv_1d"
                " (time, stock_id, open, high, low, close, volume, is_complete)"
                f" VALUES {values}"
                " ON CONFLICT (time, stock_id) DO NOTHING"
                " RETURNING time"
            ),
            params,
        )
        inserted += len(result.fetchall())

    skipped += len(payload) - inserted
    await db.commit()
    return inserted, skipped


async def ingest_bhavcopy_date(
    db: AsyncSession,
    trade_date: date,
    csv_text: str | None = None,
    *,
    historical: bool = False,
    client: httpx.AsyncClient | None = None,
) -> IngestionResult:
    """
    Download (if csv_text is None) and ingest bhavcopy for a single trade date.

    Pass csv_text to skip the download step (useful for tests and manual imports).
    `historical=True` uses backfill semantics — see `upsert_bhavcopy_rows`.
    """
    if csv_text is None:
        try:
            csv_text = await download_bhavcopy(trade_date, client=client)
        except BhavcopySourceError as exc:
            # ⭐ Reported as a distinct FAILURE, not raised. `eod_catchup` catches only
            # `httpx.HTTPError` and lets everything else abort the whole run, so one corrupt
            # date must not forfeit the rest — but it must also never read as a holiday.
            log.warning("Bhavcopy source invalid for %s: %s", trade_date, exc)
            return IngestionResult(
                status="failed",
                date=trade_date,
                rows_inserted=0,
                rows_skipped=0,
                message=f"source invalid: {exc}",
            )

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

    inserted, skipped = await upsert_bhavcopy_rows(db, rows, historical=historical)

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
