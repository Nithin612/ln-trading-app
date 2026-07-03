"""
Phase 2 stock seed script.

Data sources (all confirmed accessible, no auth required):
  1. archives.nseindia.com/content/equities/EQUITY_L.csv
     → All NSE equity symbols, ISIN, lot size, listing date, series
  2. archives.nseindia.com/content/indices/ind_nifty50list.csv
     → Nifty50 constituents + Industry (sector)
  3. archives.nseindia.com/content/indices/ind_niftybanklist.csv
     → BankNifty constituents + Industry
  4. api.kite.trade/instruments/NFO
     → F&O symbols + lot sizes (public, no auth needed)

FinNifty: hard-coded (ind_niftyfinancialserviceslist.csv returns 404 at all
tried URLs; the list is stable, updated at most quarterly on index rebalancing).

Run with:
  uv run python scripts/seed_stocks.py

Safe to re-run: uses INSERT ... ON CONFLICT DO UPDATE (upsert).
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
from datetime import date, datetime

# ── FinNifty constituents (as of May 2026 rebalancing) ───────────────────────
_FINNIFTY_SYMBOLS = {
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "BAJFINANCE",
    "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIGI", "MUTHOOTFIN", "RECLTD",
    "PFC", "SHRIRAMFIN", "CHOLAFIN", "M&MFIN", "ABCAPITAL", "MANAPPURAM",
    "LICHSGFIN", "IIFL", "UGROCAP", "CANFINHOME", "PNBHOUSING", "APTUS",
    "360ONE",
}

_NSE_ARCHIVE = "https://archives.nseindia.com/content"
_KITE_API = "https://api.kite.trade"

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64)"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8-sig")  # utf-8-sig strips BOM if present


def _csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    # Strip whitespace from keys — NSE CSVs often have " SYMBOL" with a space
    return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def _parse_listing_date(raw: str) -> date | None:
    """Handles 'DD-MMM-YYYY' format from EQUITY_L.csv."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d-%b-%Y").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_equity_universe() -> dict[str, dict]:
    """Returns {symbol: {isin, lot_size, listed_on, series}} for all NSE equities."""
    text = _fetch(f"{_NSE_ARCHIVE}/equities/EQUITY_L.csv")
    rows = _csv_rows(text)
    universe: dict[str, dict] = {}
    for row in rows:
        sym = row.get("SYMBOL", "").strip()
        series = row.get("SERIES", "").strip()
        if not sym or series not in ("EQ", "BE", "SM"):
            continue
        universe[sym] = {
            "isin": row.get("ISIN NUMBER", "").strip() or None,
            "lot_size": int(row.get("MARKET LOT", "1") or "1"),
            "listed_on": _parse_listing_date(row.get("DATE OF LISTING", "")),
            "series": series,
        }
    return universe


def fetch_index_constituents(csv_path: str) -> dict[str, str]:
    """Returns {symbol: sector} for an NSE index constituent CSV."""
    text = _fetch(f"{_NSE_ARCHIVE}/indices/{csv_path}")
    rows = _csv_rows(text)
    return {row["Symbol"]: row.get("Industry", "") for row in rows if row.get("Symbol")}


def fetch_fno_lot_sizes() -> dict[str, int]:
    """Returns {symbol: lot_size} for F&O stocks from Kite's NFO instrument dump."""
    import re

    text = _fetch(f"{_KITE_API}/instruments/NFO")
    reader = csv.DictReader(io.StringIO(text))
    lots: dict[str, int] = {}
    for row in reader:
        if row.get("instrument_type") != "FUT" or row.get("segment") != "NFO-FUT":
            continue
        tradingsymbol = row.get("tradingsymbol", "")
        # Strip expiry suffix: RELIANCE26MAYFUT → RELIANCE
        base = re.sub(r"\d{2}[A-Z]{3}FUT$", "", tradingsymbol)
        if base and base not in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
                                  "SENSEX", "BANKEX"):
            try:
                lot = int(row.get("lot_size", "0") or "0")
                if lot > 0:
                    lots[base] = lot
            except ValueError:
                pass
    return lots


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

def seed(dry_run: bool = False) -> None:  # noqa: C901
    """Fetch all sources and upsert into the database."""
    import os

    # Load env — assume .env is at project root two levels up from scripts/
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Must set DATABASE_URL before importing app modules
    if "DATABASE_URL" not in os.environ:
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    print("Fetching data from NSE and Kite…")
    equity = fetch_equity_universe()
    print(f"  Equity universe: {len(equity)} symbols")

    nifty50 = fetch_index_constituents("ind_nifty50list.csv")
    print(f"  Nifty50: {len(nifty50)} constituents")

    banknifty = fetch_index_constituents("ind_niftybanklist.csv")
    print(f"  BankNifty: {len(banknifty)} constituents")

    fno_lots = fetch_fno_lot_sizes()
    print(f"  F&O: {len(fno_lots)} stocks")

    if dry_run:
        print("Dry-run: skipping database writes.")
        return

    async def _run() -> None:  # noqa: C901
        engine = create_async_engine(db_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            # ── Upsert index records ──────────────────────────────────────────
            index_defs = [
                ("NIFTY50", "Nifty 50", "NSE"),
                ("BANKNIFTY", "Nifty Bank", "NSE"),
                ("FINNIFTY", "Nifty Financial Services", "NSE"),
            ]
            index_ids: dict[str, int] = {}
            for sym, name, exch in index_defs:
                await session.execute(
                    text("""
                        INSERT INTO indices (symbol, name, exchange, is_active)
                        VALUES (:symbol, :name, :exchange, true)
                        ON CONFLICT (symbol) DO UPDATE
                            SET name = EXCLUDED.name, is_active = true
                        RETURNING id
                    """),
                    {"symbol": sym, "name": name, "exchange": exch},
                )
                result = await session.execute(
                    text("SELECT id FROM indices WHERE symbol = :s"), {"s": sym}
                )
                index_ids[sym] = result.scalar_one()

            # ── Upsert stocks ─────────────────────────────────────────────────
            # Combine sector from index CSVs; prefer Nifty50 sector if available
            sector_map: dict[str, str] = {}
            for sym, sector in banknifty.items():
                if sector:
                    sector_map[sym] = sector
            for sym, sector in nifty50.items():
                if sector:
                    sector_map[sym] = sector

            inserted = 0
            updated = 0
            skipped = 0

            all_syms = (
                set(equity.keys()) | set(nifty50.keys())
                | set(banknifty.keys()) | set(fno_lots.keys())
            )

            for sym in all_syms:
                eq_data = equity.get(sym, {})
                is_n50 = sym in nifty50
                is_bn = sym in banknifty
                is_fn = sym in _FINNIFTY_SYMBOLS
                is_fno = sym in fno_lots
                lot = fno_lots.get(sym) or eq_data.get("lot_size", 1) or 1

                result = await session.execute(
                    text("""
                        INSERT INTO stocks (
                            symbol, exchange, isin, company_name,
                            sector, industry,
                            lot_size, tick_size,
                            is_fno, is_nifty50, is_banknifty, is_finnifty,
                            is_active, listed_on
                        )
                        VALUES (
                            :symbol, 'NSE', :isin, :company_name,
                            :sector, :sector,
                            :lot_size, 0.05,
                            :is_fno, :is_nifty50, :is_banknifty, :is_finnifty,
                            true, :listed_on
                        )
                        ON CONFLICT (symbol, exchange) DO UPDATE SET
                            isin = COALESCE(EXCLUDED.isin, stocks.isin),
                            sector = COALESCE(EXCLUDED.sector, stocks.sector),
                            industry = COALESCE(EXCLUDED.industry, stocks.industry),
                            lot_size = EXCLUDED.lot_size,
                            is_fno = EXCLUDED.is_fno,
                            is_nifty50 = EXCLUDED.is_nifty50,
                            is_banknifty = EXCLUDED.is_banknifty,
                            is_finnifty = EXCLUDED.is_finnifty,
                            listed_on = COALESCE(EXCLUDED.listed_on, stocks.listed_on),
                            updated_at = now()
                        RETURNING id, (xmax = 0) AS was_inserted
                    """),
                    {
                        "symbol": sym,
                        "isin": eq_data.get("isin"),
                        "company_name": (
                            nifty50.get(sym) or banknifty.get(sym) or sym
                        ),
                        "sector": sector_map.get(sym),
                        "lot_size": lot,
                        "is_fno": is_fno,
                        "is_nifty50": is_n50,
                        "is_banknifty": is_bn,
                        "is_finnifty": is_fn,
                        "listed_on": eq_data.get("listed_on"),
                    },
                )
                row = result.fetchone()
                if row:
                    stock_id = row[0]
                    was_inserted = row[1]
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1

                    # ── Update index memberships ──────────────────────────────
                    memberships = []
                    if is_n50:
                        memberships.append("NIFTY50")
                    if is_bn:
                        memberships.append("BANKNIFTY")
                    if is_fn:
                        memberships.append("FINNIFTY")

                    for idx_sym in memberships:
                        idx_id = index_ids[idx_sym]
                        await session.execute(
                            text("""
                                INSERT INTO index_constituents (index_id, stock_id, added_on)
                                VALUES (:iid, :sid, CURRENT_DATE)
                                ON CONFLICT (index_id, stock_id, added_on) DO NOTHING
                            """),
                            {"iid": idx_id, "sid": stock_id},
                        )
                else:
                    skipped += 1

            await session.commit()
            print(f"\nDone. Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}")

        await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed NSE stock universe")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but skip DB writes")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
