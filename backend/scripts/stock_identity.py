"""D0 — export or verify the stock-identity pin (`backend/seed/stock_identity.csv`).

    uv run python scripts/stock_identity.py --verify    # default; exit 1 on conflict
    uv run python scripts/stock_identity.py --export    # rewrite the pin

⭐ **Why this exists.** Every `stocks.id` was reassigned during the 2026-09-07
emergency rebuild, which is why the documented reversal SQL in
`deactivate_dead_stocks.py` now names the wrong companies (plan §20/2). The pin lets
a rebuild FROM SOURCE reproduce the same id → symbol mapping, so artifacts keyed on
an id — probe dumps, forensic tables, analysis output — survive it.

⚠ **`--verify` fails only on a CONFLICT** (a symbol whose id moved). New listings and
delistings are ordinary churn and are reported, not failed: re-export to adopt them.

**Restore procedure, for the rebuild this is insurance against:** load the pin, insert
`stocks` with EXPLICIT ids, then advance the sequence past the maximum
(`SELECT setval(pg_get_serial_sequence('stocks','id'), (SELECT max(id) FROM stocks))`)
before seeding or backfilling anything. Skip the setval and the next insert collides.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.stock_identity import (  # noqa: E402
    PinnedStock,
    diff,
    parse,
    serialise,
)
from sqlalchemy import text  # noqa: E402

PIN_PATH = Path(__file__).resolve().parents[1] / "seed" / "stock_identity.csv"


async def _live_rows() -> list[PinnedStock]:
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT id, symbol, isin, created_at::date AS first_seen"
                    " FROM stocks WHERE exchange = 'NSE' ORDER BY symbol"
                )
            )
        ).fetchall()
    return [
        PinnedStock(
            stock_id=int(r.id),
            symbol=str(r.symbol),
            isin=(str(r.isin) if r.isin else None),
            first_seen=str(r.first_seen),
        )
        for r in rows
    ]


async def _export() -> int:
    rows = await _live_rows()
    PIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIN_PATH.write_text(serialise(rows))
    print(f"wrote {len(rows)} rows to {PIN_PATH}")
    return 0


async def _verify() -> int:
    if not PIN_PATH.exists():
        print(f"no pin file at {PIN_PATH} — run with --export first", file=sys.stderr)
        return 1
    pinned = parse(PIN_PATH.read_text())
    live = {r.symbol: r.stock_id for r in await _live_rows()}
    d = diff(pinned, live)

    print(f"pinned {len(pinned)} · live {len(live)}")
    if d.added:
        print(f"  + {len(d.added)} new listing(s) (expected; re-export to adopt): "
              f"{', '.join(d.added[:10])}{'…' if len(d.added) > 10 else ''}")
    if d.missing:
        print(f"  - {len(d.missing)} pinned name(s) absent from the DB: "
              f"{', '.join(d.missing[:10])}{'…' if len(d.missing) > 10 else ''}")
    if d.conflicts:
        print(f"\n⛔ {len(d.conflicts)} ID CONFLICT(S) — every artifact keyed on these "
              "ids now points at a different company:", file=sys.stderr)
        for symbol, pinned_id, live_id in d.conflicts[:20]:
            print(f"    {symbol}: pinned {pinned_id} -> live {live_id}", file=sys.stderr)
        return 1
    print("✅ no id conflicts")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="export or verify the stock-identity pin")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--export", action="store_true", help="rewrite the pin from the DB")
    g.add_argument("--verify", action="store_true", help="compare the DB against the pin")
    args = p.parse_args()
    return asyncio.run(_export() if args.export else _verify())


if __name__ == "__main__":
    raise SystemExit(main())
