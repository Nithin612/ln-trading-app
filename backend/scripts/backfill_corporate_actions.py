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
from app.models.stock import Stock  # noqa: E402
from app.services.nse_corporate_actions import (  # noqa: E402
    fetch_corporate_actions,
    ingest_corporate_actions,
)
from sqlalchemy import select  # noqa: E402


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
            # ⚠ A dry run must report what the REAL run would do, not merely what it fetched.
            # The first version printed `inserted 0 · unknown_symbol 0`, which reads as
            # "nothing would be inserted" when those counters were simply never computed —
            # a zero that means "not measured" presented as a zero that means "none".
            parsed, unsupported = await fetch_corporate_actions(a, b)
            async with AsyncSessionFactory() as db:
                known = set(
                    (await db.execute(
                        select(Stock.symbol).where(
                            Stock.symbol.in_({x.symbol for x in parsed})
                        )
                    )).scalars().all()
                ) if parsed else set()
            would = sum(1 for x in parsed if x.symbol in known)
            totals["parsed"] += len(parsed)
            totals["unsupported"] += len(unsupported)
            totals["inserted"] += would
            totals["unknown_symbol"] += len(parsed) - would
            print(f"[{i}] {a}→{b}  parsed {len(parsed):>3}  would insert {would:>3}  "
                  f"unsupported {len(unsupported):>4}", flush=True)
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

    label = "WOULD INSERT" if dry else "inserted"
    print(
        f"\n{'DRY RUN — nothing written. ' if dry else ''}"
        f"parsed {totals['parsed']} · {label} {totals['inserted']} · "
        f"not in our universe {totals['unknown_symbol']} · "
        f"unsupported {totals['unsupported']}"
        + ("" if dry else f" · already present {totals['already_present']}"
                          f" · manual conflicts {totals['manual_conflicts']}")
    )
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
