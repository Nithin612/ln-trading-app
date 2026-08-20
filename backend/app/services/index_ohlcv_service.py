"""Index EOD OHLC recorder — MCE slice 2.

The keystone the relative-strength overlay (`app/signals/sector_rs.py`) needs: a daily
price series for the market/sector indices. Source = the SAME NSE indices bhavcopy CSV
the India-VIX recorder already downloads (`ind_close_all_DDMMYYYY.csv`) — that one file
carries every NSE index (Nifty 50, Nifty Bank, Nifty Financial Services, all sectorals),
so this needs **no Kite token / historical API**, and it self-heals through the EOD
catch-up like the other feeds.

Which indices to capture is driven by the existing `indices` registry (`Index.name` is the
exact CSV "Index Name"), so adding a sector index later is one registry row + no code change
— but only its GOING-FORWARD days are captured automatically: the EOD catch-up marks a day
"present" if ANY index has a row for it, so a newly-registered index's HISTORY needs an
explicit backfill (re-run this ingester per past date), not the catch-up self-heal. Upserts
are idempotent (`on_conflict_do_nothing` on the (index_id, trade_date) PK), mirroring
`vix_service.ingest_vix_date`.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Index, IndexOhlcvDaily

# Reuse the VIX recorder's downloader + decimal parser — same CSV, one source of truth.
from app.services.vix_service import _dec_field, download_indices_csv

log = logging.getLogger(__name__)


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_index_rows(
    csv_text: str, name_to_id: dict[str, int]
) -> list[dict[str, object]]:
    """Rows for the registered indices from the NSE indices bhavcopy CSV.

    `name_to_id` maps a lower-cased CSV "Index Name" → our `indices.id`. Only registered
    names are kept (VIX and unlisted indices are ignored); a row with no close or an
    unparseable date is skipped (never emitted as a partial). Pure/sync so it tests off a
    fixture."""
    out: list[dict[str, object]] = []
    seen: set[tuple[int, date]] = set()
    reader = csv.DictReader(io.StringIO(csv_text))
    for raw in reader:
        name = (raw.get("Index Name") or "").strip().lower()
        index_id = name_to_id.get(name)
        if index_id is None:
            continue
        close = _dec_field(raw, "Closing Index Value")
        trade_date = _parse_date(raw.get("Index Date") or "")
        if close is None or trade_date is None:
            continue
        key = (index_id, trade_date)
        if key in seen:  # a duplicate name in one file — keep the first
            continue
        seen.add(key)
        out.append(
            {
                "index_id": index_id,
                "trade_date": trade_date,
                "open": _dec_field(raw, "Open Index Value"),
                "high": _dec_field(raw, "High Index Value"),
                "low": _dec_field(raw, "Low Index Value"),
                "close": close,
            }
        )
    return out


async def _registry_name_to_id(db: AsyncSession) -> dict[str, int]:
    """Active indices → {lower-cased CSV name: id}."""
    rows = (await db.execute(select(Index.id, Index.name).where(Index.is_active.is_(True)))).all()
    return {name.strip().lower(): id_ for id_, name in rows}


async def ingest_index_ohlcv_date(
    db: AsyncSession,
    trade_date: date,
    csv_text: str | None = None,
) -> dict[str, object]:
    """Download (unless csv_text given) and upsert index OHLC for one date.

    Signature matches the other EOD ingesters (`ingest_vix_date`) so it drops straight into
    the EOD catch-up loop."""
    def _skip(message: str) -> dict[str, object]:
        return {"status": "skipped", "date": str(trade_date), "message": message}

    name_to_id = await _registry_name_to_id(db)
    if not name_to_id:
        return _skip("no indices registered")

    if csv_text is None:
        csv_text = await download_indices_csv(trade_date)
    if csv_text is None:
        return _skip("indices csv not available")

    rows = parse_index_rows(csv_text, name_to_id)
    if not rows:
        return _skip("no registered index rows")

    result = await db.execute(pg_insert(IndexOhlcvDaily).values(rows).on_conflict_do_nothing())
    await db.commit()
    inserted = int(getattr(result, "rowcount", 0) or 0)
    log.info(
        "Index OHLC %s: %d row(s) parsed, %d inserted",
        trade_date,
        len(rows),
        inserted,
    )
    return {
        "status": "ok",
        "date": str(trade_date),
        "parsed": len(rows),
        "inserted": inserted,
    }
