"""NSE F&O bhavcopy (UDiFF) downloader, parser, and upsert service.

Since July 2024 NSE publishes derivatives EOD data in the UDiFF common
format, zipped:

  https://nsearchives.nseindia.com/content/fo/
      BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip

Columns used (UDiFF names):
  TradDt, FinInstrmTp (STF|IDF = stock/index futures, STO|IDO = options),
  TckrSymb, XpryDt, StrkPric, OptnTp (CE|PE), OpnPric, HghPric, LwPric,
  ClsPric, SttlmPric, UndrlygPric, OpnIntrst, ChngInOpnIntrst, TtlTradgVol

Everything is upserted with ON CONFLICT DO NOTHING so re-running a date is
always idempotent. This recorder exists to bootstrap options analytics
history (EOD IV, IV-rank, PCR, max pain) long before Phase 4 consumes it.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fo_data import FoBhavcopy
from app.services.bhavcopy_service import _NSE_HEADERS

log = logging.getLogger(__name__)

_FO_URL_PATTERN = (
    "https://nsearchives.nseindia.com/content/fo/"
    "BhavCopy_NSE_FO_0_0_0_{date}_F_0000.csv.zip"
)

# UDiFF instrument-type → our instrument column
_FUTURE_TYPES = {"STF", "IDF"}
_OPTION_TYPES = {"STO", "IDO"}


@dataclass
class FoBhavRow:
    trade_date: date
    symbol: str
    instrument: str  # FUT | CE | PE
    expiry_date: date
    strike: Decimal
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    settle_price: Decimal | None
    underlying_close: Decimal | None
    volume_contracts: int | None
    open_interest: int | None
    change_in_oi: int | None


def _dec(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned == "-":
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _int(raw: str | None) -> int | None:
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned == "-":
        return None
    try:
        return int(float(cleaned))
    except (ValueError, OverflowError):
        return None


def _date(raw: str | None) -> date | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def parse_fo_bhavcopy_csv(text: str) -> list[FoBhavRow]:
    """Parse UDiFF F&O bhavcopy CSV text into validated rows.

    Keeps stock + index futures and options; skips malformed rows.
    """
    reader = csv.DictReader(io.StringIO(text))
    rows: list[FoBhavRow] = []

    for raw in reader:
        fin_type = (raw.get("FinInstrmTp") or "").strip().upper()
        if fin_type in _FUTURE_TYPES:
            instrument = "FUT"
            strike = Decimal("0")
        elif fin_type in _OPTION_TYPES:
            instrument = (raw.get("OptnTp") or "").strip().upper()
            if instrument not in ("CE", "PE"):
                continue
            strike_v = _dec(raw.get("StrkPric"))
            if strike_v is None:
                continue
            strike = strike_v
        else:
            continue  # other segments (currency etc.)

        symbol = (raw.get("TckrSymb") or "").strip().upper()
        trade_date = _date(raw.get("TradDt"))
        expiry_date = _date(raw.get("XpryDt"))
        if not symbol or trade_date is None or expiry_date is None:
            continue

        rows.append(
            FoBhavRow(
                trade_date=trade_date,
                symbol=symbol,
                instrument=instrument,
                expiry_date=expiry_date,
                strike=strike,
                open=_dec(raw.get("OpnPric")),
                high=_dec(raw.get("HghPric")),
                low=_dec(raw.get("LwPric")),
                close=_dec(raw.get("ClsPric")),
                settle_price=_dec(raw.get("SttlmPric")),
                underlying_close=_dec(raw.get("UndrlygPric")),
                volume_contracts=_int(raw.get("TtlTradgVol")),
                open_interest=_int(raw.get("OpnIntrst")),
                change_in_oi=_int(raw.get("ChngInOpnIntrst")),
            )
        )

    return rows


async def download_fo_bhavcopy(trade_date: date) -> str | None:
    """Download and unzip the F&O bhavcopy for a date; None on holiday/miss."""
    url = _FO_URL_PATTERN.format(date=trade_date.strftime("%Y%m%d"))

    async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=60, follow_redirects=True) as c:
        try:
            await c.get("https://www.nseindia.com/", timeout=10)  # cookie priming
        except httpx.HTTPError:
            pass
        resp = await c.get(url)

    if resp.status_code != 200:
        log.info("F&O bhavcopy not available for %s (HTTP %s)", trade_date, resp.status_code)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                log.warning("F&O bhavcopy zip for %s had no CSV member", trade_date)
                return None
            return zf.read(csv_names[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        log.info("F&O bhavcopy for %s was not a zip (likely blocked/holiday)", trade_date)
        return None


async def upsert_fo_rows(db: AsyncSession, rows: list[FoBhavRow]) -> int:
    """Idempotent bulk insert; returns number of newly inserted rows."""
    if not rows:
        return 0

    inserted = 0
    # Chunked executemany keeps parameter counts sane on big files (~100k rows)
    chunk = 2000
    for i in range(0, len(rows), chunk):
        values = [
            {
                "trade_date": r.trade_date,
                "symbol": r.symbol,
                "instrument": r.instrument,
                "expiry_date": r.expiry_date,
                "strike": r.strike,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "settle_price": r.settle_price,
                "underlying_close": r.underlying_close,
                "volume_contracts": r.volume_contracts,
                "open_interest": r.open_interest,
                "change_in_oi": r.change_in_oi,
            }
            for r in rows[i : i + chunk]
        ]
        stmt = pg_insert(FoBhavcopy).values(values).on_conflict_do_nothing()
        result = await db.execute(stmt)
        inserted += int(getattr(result, "rowcount", 0) or 0)

    await db.commit()
    return inserted


async def ingest_fo_bhavcopy_date(
    db: AsyncSession,
    trade_date: date,
    csv_text: str | None = None,
) -> dict[str, object]:
    """Download (unless csv_text given) and ingest one date. Idempotent."""
    if csv_text is None:
        csv_text = await download_fo_bhavcopy(trade_date)
    if csv_text is None:
        return {"status": "skipped", "date": str(trade_date), "inserted": 0,
                "message": "not available (holiday/weekend/blocked)"}

    rows = parse_fo_bhavcopy_csv(csv_text)
    if not rows:
        return {"status": "skipped", "date": str(trade_date), "inserted": 0,
                "message": "no valid derivative rows in CSV"}

    inserted = await upsert_fo_rows(db, rows)
    log.info("F&O bhavcopy %s: %d/%d rows inserted", trade_date, inserted, len(rows))
    return {"status": "ok", "date": str(trade_date), "inserted": inserted,
            "parsed": len(rows)}
