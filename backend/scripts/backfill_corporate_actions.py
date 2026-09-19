"""Item 16 — populate `corporate_actions` from NSE, the authority.

    uv run python scripts/backfill_corporate_actions.py --from 2023-07-03 --to 2026-09-19
    uv run python scripts/backfill_corporate_actions.py --from ... --to ... --dry-run

⚠ Chunked by month because the endpoint's window is not documented and a long range has not
been verified to return everything. Chunking is also what makes a partial run resumable.

⚠ **Writes to the database unless `--dry-run`.** CLAUDE.md: ask before writing live data.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.nse_corporate_actions import (  # noqa: E402
    fetch_corporate_actions,
    ingest_corporate_actions,
)


def _months(start: date, end: date) -> list[tuple[date, date]]:
    out, cur = [], start
    while cur <= end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((cur, min(nxt - timedelta(days=1), end)))
        cur = nxt
    return out


async def run(start: date, end: date, dry: bool, delay: float) -> int:
    totals = {"parsed": 0, "inserted": 0, "unsupported": 0, "unknown_symbol": 0,
              "already_present": 0, "manual_conflicts": 0}
    conflicts: list[str] = []
    for i, (a, b) in enumerate(_months(start, end), 1):
        if dry:
            parsed, unsupported = await fetch_corporate_actions(a, b)
            totals["parsed"] += len(parsed)
            totals["unsupported"] += len(unsupported)
            print(f"[{i}] {a}→{b}  parsed {len(parsed):>3}  unsupported {len(unsupported):>3}",
                  flush=True)
        else:
            async with AsyncSessionFactory() as db:
                out = await ingest_corporate_actions(db, a, b)
                await db.commit()
            for k in totals:
                v = out.get(k, 0)
                totals[k] += v if isinstance(v, int) else 0
            conflicts += [str(c) for c in out.get("conflict_rows", [])]  # type: ignore[union-attr]
            print(f"[{i}] {a}→{b}  parsed {out['parsed']:>3}  inserted {out['inserted']:>3}  "
                  f"unsupported {out['unsupported']:>3}", flush=True)
        await asyncio.sleep(delay)

    print("\n" + " · ".join(f"{k} {v}" for k, v in totals.items()))
    if conflicts:
        print("\n⚠ MANUAL/NSE RATIO CONFLICTS — the human row was kept, investigate each:")
        for c in conflicts:
            print(f"    {c}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--dry-run", action="store_true", help="fetch and report; write nothing")
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    return asyncio.run(
        run(date.fromisoformat(a.start), date.fromisoformat(a.end), a.dry_run, a.delay)
    )


if __name__ == "__main__":
    raise SystemExit(main())
