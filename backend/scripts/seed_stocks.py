"""
Phase 2 stock seed script.

Data sources (all confirmed accessible, no auth required):
  1. archives.nseindia.com/content/equities/EQUITY_L.csv
     → All NSE equity symbols, ISIN, lot size, listing date, series
  2. archives.nseindia.com/content/indices/ind_nifty50list.csv
     → Nifty50 constituents + Industry (sector)
  3. archives.nseindia.com/content/indices/ind_niftybanklist.csv
     → BankNifty constituents + Industry
  4. archives.nseindia.com/content/indices/ind_nifty500list.csv
     → the widest free sector source NSE publishes as a flat CSV. Without it
       sector coverage is capped at the ~59 names in (2) and (3), which is why
       the screener's sector filter used to match 2.5% of the universe.
       Non-fatal: an outage narrows coverage, it does not block a reseed.
  5. api.kite.trade/instruments/NFO
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
    """Returns {symbol: {isin, company_name, lot_size, listed_on, series}}.

    `NAME OF COMPANY` was present in this CSV all along but never read, which is
    why every stock's `company_name` was either its own ticker or — for the 59
    index members — the *sector* string (the caller was indexing a
    {symbol: industry} map as if it held names). ADANIENT was literally called
    "Metals & Mining".
    """
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
            "company_name": row.get("NAME OF COMPANY", "").strip() or None,
            "lot_size": int(row.get("MARKET LOT", "1") or "1"),
            "listed_on": _parse_listing_date(row.get("DATE OF LISTING", "")),
            "series": series,
        }
    return universe


def fetch_index_constituents(csv_path: str) -> dict[str, str]:
    """Returns {symbol: sector} for an NSE index constituent CSV.

    The value is the CSV's `Industry` column — NSE's sector label. It is NOT a
    company name; callers that need one must use the equity universe.
    """
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
# Rename planning (pure — the DB-touching part lives in seed())
# ---------------------------------------------------------------------------

def plan_renames(
    equity: dict[str, dict],
    all_syms: set[str] | frozenset[str],
    existing_by_isin: dict[str, tuple[int, str]],
    existing_symbols: set[str] | frozenset[str],
) -> tuple[list[tuple[str, str, str, int]], list[tuple[str, str, str]]]:
    """Decide which existing rows are the same company under a NEW ticker.

    Returns `(renames, collisions)` where a rename is
    `(isin, old_symbol, new_symbol, stock_id)` and a collision is
    `(isin, existing_symbol, incoming_symbol)`.

    Why this exists: the upsert conflicts on `(symbol, exchange)`, but
    `uq_stocks_isin` must hold too. When NSE renames a ticker, the CSV brings the
    NEW symbol carrying the OLD row's ISIN — so the insert dies on the ISIN
    constraint and the entire reseed rolls back. That is why this script had
    quietly stopped being re-runnable (AMIRCHAND → AEROPLANE, INE05TO01019).

    A rename is the SAME company, so the row is renamed **in place**: it keeps
    its id, and with it every OHLCV bar, signal and position pointing at it.
    Inserting a fresh row would strand all of that under a ticker NSE no longer
    publishes.

    When BOTH tickers already exist as rows, deciding which history is canonical
    is not a seed script's call — that is reported as a collision and left alone
    (the caller then writes the incoming row without its ISIN).
    """
    renames: list[tuple[str, str, str, int]] = []
    collisions: list[tuple[str, str, str]] = []
    live_symbols = set(existing_symbols)
    # An ISIN can only be spent once. Without this, two CSV symbols claiming one
    # ISIN both plan a rename of the SAME row id and the second UPDATE silently
    # overwrites the first — one row, two names, no error. Caught by test.
    claimed: set[str] = set()

    # Sorted for determinism: two symbols claiming one ISIN must resolve the
    # same way on every run, or a reseed becomes order-dependent.
    for sym in sorted(all_syms):
        isin = equity.get(sym, {}).get("isin")
        if not isin:
            continue
        owner = existing_by_isin.get(isin)
        if owner is None:
            continue
        stock_id, old_symbol = owner
        if old_symbol == sym:
            continue
        if sym in live_symbols or isin in claimed:
            collisions.append((isin, old_symbol, sym))
            continue
        claimed.add(isin)
        live_symbols.discard(old_symbol)
        live_symbols.add(sym)
        renames.append((isin, old_symbol, sym, stock_id))
    return renames, collisions


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

    # Nifty 500 is the widest free sector source NSE publishes as a flat CSV.
    # Without it, sector coverage is capped at the ~59 names in the two index
    # files above — which is exactly why the screener's sector filter matched
    # 2.5% of the universe. Non-fatal: an NSE outage should not block a reseed.
    try:
        nifty500 = fetch_index_constituents("ind_nifty500list.csv")
        print(f"  Nifty500: {len(nifty500)} constituents (sector source)")
    except Exception as exc:  # noqa: BLE001 - reseed must survive a dead CSV
        print(f"  Nifty500: UNAVAILABLE ({exc}) — sector coverage stays narrow")
        nifty500 = {}

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
            # Sector from the index CSVs, widest source first so the narrower,
            # more curated lists win on overlap (Nifty50 last = highest priority).
            sector_map: dict[str, str] = {}
            for source in (nifty500, banknifty, nifty50):
                for sym, sector in source.items():
                    if sector:
                        sector_map[sym] = sector

            inserted = 0
            updated = 0
            skipped = 0

            all_syms = (
                set(equity.keys()) | set(nifty50.keys())
                | set(banknifty.keys()) | set(fno_lots.keys())
            )

            # ── Symbol renames, keyed on ISIN (see plan_renames) ─────────────
            existing_by_isin = {
                r[0]: (r[1], r[2])
                for r in (
                    await session.execute(
                        text("SELECT isin, id, symbol FROM stocks WHERE isin IS NOT NULL")
                    )
                ).fetchall()
            }
            existing_symbols = {
                r[0]
                for r in (await session.execute(text("SELECT symbol FROM stocks"))).fetchall()
            }
            renamed, collided = plan_renames(equity, all_syms, existing_by_isin, existing_symbols)
            for _isin, _old, new_symbol, stock_id in renamed:
                await session.execute(
                    text(
                        "UPDATE stocks SET symbol = :new, updated_at = now() WHERE id = :sid"
                    ),
                    {"new": new_symbol, "sid": stock_id},
                )
            if renamed:
                await session.flush()
            _collided_symbols = {new for _isin, _old, new in collided}

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
                            -- Was absent, so a reseed could never repair a name
                            -- once written. COALESCE keeps the existing value
                            -- only when NSE has nothing better to offer.
                            company_name = COALESCE(
                                EXCLUDED.company_name, stocks.company_name
                            ),
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
                        # An ISIN another live row already owns must not be
                        # written here, or the reseed dies on uq_stocks_isin and
                        # rolls back everything. The collision is reported below.
                        "isin": (
                            None
                            if sym in _collided_symbols
                            else eq_data.get("isin")
                        ),
                        # The equity master is the ONLY source of a real name.
                        # The index maps hold {symbol: industry}; reading them
                        # here is what put a sector in the company_name column.
                        "company_name": eq_data.get("company_name") or sym,
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
            # Renames change what a ticker MEANS, so they are never silent.
            if renamed:
                print(f"\nRenamed {len(renamed)} symbol(s) in place (history preserved):")
                for isin, old, new, _sid in renamed:
                    print(f"  {old} → {new}   ({isin})")
            if collided:
                print(
                    f"\n{len(collided)} ISIN collision(s) LEFT ALONE — both tickers already"
                    " exist as rows, so merging them is your call:"
                )
                for isin, old, new in collided:
                    print(f"  {isin}: existing {old} vs incoming {new} (ISIN not written)")

        await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed NSE stock universe")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but skip DB writes")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
