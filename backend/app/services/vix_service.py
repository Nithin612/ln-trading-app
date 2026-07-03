"""India VIX EOD recorder.

Source: the NSE indices bhavcopy (same archive host as the equity bhavcopy,
far more reliable than the JSON API):

  https://nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv

Columns: "Index Name", "Index Date" (DD-MM-YYYY), "Open Index Value",
"High Index Value", "Low Index Value", "Closing Index Value", ...
We keep only the "India VIX" row. VIX is the interim IV-regime proxy until
self-recorded chain history is deep enough (UPGRADE_PLAN.md, F&O phase).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fo_data import IndiaVixDaily
from app.services.bhavcopy_service import _NSE_HEADERS

log = logging.getLogger(__name__)

_INDICES_URL_PATTERN = (
    "https://nsearchives.nseindia.com/content/indices/ind_close_all_{date}.csv"
)
_VIX_INDEX_NAME = "india vix"


def _dec_field(row: dict[str, str], key: str) -> Decimal | None:
    v = (row.get(key) or "").strip().replace(",", "")
    if not v or v == "-":
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def parse_vix_row(text: str) -> dict[str, object] | None:
    """Extract the India VIX row from the indices bhavcopy CSV, or None."""
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        name = (raw.get("Index Name") or "").strip().lower()
        if name != _VIX_INDEX_NAME:
            continue

        close = _dec_field(raw, "Closing Index Value")
        date_raw = (raw.get("Index Date") or "").strip()
        trade_date: date | None = None
        for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
            try:
                trade_date = datetime.strptime(date_raw, fmt).date()
                break
            except ValueError:
                continue

        if close is None or trade_date is None:
            return None
        return {
            "trade_date": trade_date,
            "open": _dec_field(raw, "Open Index Value"),
            "high": _dec_field(raw, "High Index Value"),
            "low": _dec_field(raw, "Low Index Value"),
            "close": close,
        }
    return None


async def download_indices_csv(trade_date: date) -> str | None:
    url = _INDICES_URL_PATTERN.format(date=trade_date.strftime("%d%m%Y"))
    async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=30, follow_redirects=True) as c:
        try:
            await c.get("https://www.nseindia.com/", timeout=10)
        except httpx.HTTPError:
            pass
        resp = await c.get(url)

    if resp.status_code != 200 or "text/html" in resp.headers.get("content-type", ""):
        log.info("Indices bhavcopy not available for %s", trade_date)
        return None
    return resp.text


async def ingest_vix_date(
    db: AsyncSession,
    trade_date: date,
    csv_text: str | None = None,
) -> dict[str, object]:
    """Download (unless csv_text given) and upsert India VIX for one date."""
    if csv_text is None:
        csv_text = await download_indices_csv(trade_date)
    if csv_text is None:
        return {"status": "skipped", "date": str(trade_date),
                "message": "indices csv not available"}

    row = parse_vix_row(csv_text)
    if row is None:
        return {"status": "skipped", "date": str(trade_date),
                "message": "India VIX row not found"}

    stmt = pg_insert(IndiaVixDaily).values(**row).on_conflict_do_nothing()
    result = await db.execute(stmt)
    await db.commit()
    inserted = bool(int(getattr(result, "rowcount", 0) or 0))
    log.info("India VIX %s: close=%s (%s)", row["trade_date"], row["close"],
             "inserted" if inserted else "already present")
    return {"status": "ok", "date": str(row["trade_date"]),
            "close": str(row["close"]), "inserted": inserted}
