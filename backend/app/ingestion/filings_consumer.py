"""Corporate filings ingestion — Phase 6.

Polls NSE and BSE corporate announcements every 60 seconds during market hours.
Each run is idempotent: filing_time + stock_id + source is the natural dedup key.

NSE endpoint: https://www.nseindia.com/api/corporate-announcements?index=equities
BSE endpoint: https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?
              pageno=1&subcategory=-1&category=Corp+Action&scrip_cd=&segment=0&strdate=&enddate=&type=C

Both endpoints return JSON with announcement headline + timestamp.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.filing import CorporateFiling
from app.models.stock import Stock

log = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

_BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}

# ── Keyword classifier ───────────────────────────────────────────────────────

_CLASSIFIERS: list[tuple[str, re.Pattern[str]]] = [
    ("earnings",      re.compile(r"financial result|quarterly result|annual result", re.I)),
    ("board_meeting", re.compile(r"board meeting|board of directors", re.I)),
    ("dividend",      re.compile(r"dividend|interim dividend|final dividend", re.I)),
    ("split",         re.compile(r"stock split|sub.?division of shares", re.I)),
    ("bonus",         re.compile(r"bonus share|bonus issue", re.I)),
    ("merger",        re.compile(
        r"merger|amalgamation|demerger|acquisition|scheme of arrangement", re.I
    )),
    ("agm",           re.compile(r"\bAGM\b|annual general meeting", re.I)),
    ("rating_change", re.compile(
        r"credit rating|rating upgrade|rating downgrade|rating reaffirm", re.I
    )),
]


def classify_headline(headline: str) -> str:
    for filing_type, pattern in _CLASSIFIERS:
        if pattern.search(headline):
            return filing_type
    return "other"


# ── Symbol → stock_id lookup ─────────────────────────────────────────────────

async def _build_symbol_map(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(Stock.symbol, Stock.id).where(Stock.is_active.is_(True)))
    return {row[0]: row[1] for row in result.all()}


# ── Dedup helper ─────────────────────────────────────────────────────────────

async def _already_stored(
    db: AsyncSession, stock_id: int, filing_time: datetime, source: str
) -> bool:
    result = await db.execute(
        select(CorporateFiling.id).where(
            CorporateFiling.stock_id == stock_id,
            CorporateFiling.filing_time == filing_time,
            CorporateFiling.source == source,
        ).limit(1)
    )
    return result.scalar() is not None


# ── NSE fetcher ──────────────────────────────────────────────────────────────

async def _fetch_nse_filings(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch the NSE corporate announcements feed (equities segment)."""
    # Establish session cookie first
    try:
        await client.get("https://www.nseindia.com/", headers=_NSE_HEADERS, timeout=10)
    except Exception:
        pass  # Cookie warmup; ignore failures

    try:
        resp = await client.get(
            "https://www.nseindia.com/api/corporate-announcements?index=equities",
            headers=_NSE_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items: list[dict[str, Any]] = data if isinstance(data, list) else data.get("data", [])
        return items
    except Exception as exc:
        log.warning("NSE filings fetch failed: %s", exc)
        return []


def _parse_nse_filing(item: dict[str, Any]) -> tuple[str, str, str, datetime] | None:
    """Extract (symbol, headline, body, filing_time) from one NSE announcement record."""
    symbol = (item.get("symbol") or item.get("smIndustry") or "").strip().upper()
    headline = (item.get("desc") or item.get("subject") or "").strip()
    raw_body: str | None = ((item.get("attchmntFile") or "").strip()) or None

    # NSE timestamps: "28-Apr-2025 15:27:30" or ISO
    raw_ts = item.get("bcastDate") or item.get("an_dt") or ""
    filing_time: datetime | None = None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            filing_time = datetime.strptime(str(raw_ts).strip(), fmt).replace(tzinfo=UTC)
            break
        except ValueError:
            continue

    if not symbol or not headline or filing_time is None:
        return None
    return symbol, headline, str(raw_body), filing_time


# ── BSE fetcher ──────────────────────────────────────────────────────────────

async def _fetch_bse_filings(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch BSE corporate announcements."""
    today = date.today().strftime("%Y%m%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    url = (
        "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
        f"?pageno=1&subcategory=-1&category=Corp+Action&scrip_cd="
        f"&segment=0&strdate={yesterday}&enddate={today}&type=C"
    )
    try:
        resp = await client.get(url, headers=_BSE_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("Table", [])  # type: ignore[no-any-return]
    except Exception as exc:
        log.warning("BSE filings fetch failed: %s", exc)
        return []


def _parse_bse_filing(item: dict[str, Any]) -> tuple[str, str, str | None, datetime] | None:
    """Extract (symbol, headline, body, filing_time) from one BSE announcement record."""
    symbol = (item.get("scrip_cd") or "").strip().upper()
    # BSE also provides ISIN; try short_name for symbol cross-reference
    if not symbol:
        symbol = (item.get("short_name") or "").strip().upper()
    headline = (item.get("HEADLINE") or item.get("newssub") or "").strip()
    body = item.get("NEWSSUB") or None

    raw_ts = item.get("NEWS_DT") or item.get("DissemDT") or ""
    filing_time: datetime | None = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            filing_time = datetime.strptime(str(raw_ts).strip(), fmt).replace(tzinfo=UTC)
            break
        except ValueError:
            continue

    if not symbol or not headline or filing_time is None:
        return None
    return symbol, headline, body, filing_time


# ── Main entry point ─────────────────────────────────────────────────────────

async def ingest_filings(db: AsyncSession) -> int:
    """Poll NSE + BSE, classify, dedup, and persist new filings. Returns count inserted."""
    symbol_map = await _build_symbol_map(db)
    inserted = 0

    async with httpx.AsyncClient() as client:
        nse_raw = await _fetch_nse_filings(client)
        # offset BSE by 30 s via sequential await — avoids hammering both at once
        bse_raw = await _fetch_bse_filings(client)

    batches: list[tuple[str, list[dict[str, Any]], str]] = [
        ("NSE", nse_raw, "NSE"),
        ("BSE", bse_raw, "BSE"),
    ]

    for label, items, source in batches:
        for item in items:
            parsed = _parse_nse_filing(item) if label == "NSE" else _parse_bse_filing(item)
            if parsed is None:
                continue
            symbol, headline, body, filing_time = parsed

            stock_id = symbol_map.get(symbol)
            if stock_id is None:
                continue  # stock not in our universe

            if await _already_stored(db, stock_id, filing_time, source):
                continue

            filing_type = classify_headline(headline)
            filing = CorporateFiling(
                stock_id=stock_id,
                filing_type=filing_type,
                headline=headline,
                body=body or None,
                filing_date=filing_time.date(),
                filing_time=filing_time,
                source=source,
            )
            db.add(filing)
            inserted += 1

    if inserted:
        await db.commit()
        log.info("Filings consumer: inserted %d new filings", inserted)
    return inserted
