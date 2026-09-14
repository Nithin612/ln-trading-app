"""U11 — withdraw signals without deleting them.

    uv run python scripts/quarantine_signals.py --list
    uv run python scripts/quarantine_signals.py --before 2026-09-12 \
        --reason "minted against the broken universe (2026-09-07..09-12)"
    uv run python scripts/quarantine_signals.py --release <signal-id>

⭐ **Withdrawn, not deleted.** A quarantined signal keeps its row, its factor scores and
its outcome — it is the forensic record of what the system actually emitted. Deleting it
would destroy the evidence of the failure that produced it.

⭐ **And withdrawn VISIBLY.** The quarantine is a `Restriction`, so the list still shows
the signal, flagged `⊘ blocked` with the reason verbatim, and the order path 409s with
the same words. A filtered-out signal would simply vanish — the invisibility PART XVIII
objects to.

⚠ `signals.status` is deliberately untouched: it is a LIFECYCLE field the sweeper
overwrites, so a verdict parked there can be silently undone, and "expired by time" would
become indistinguishable from "withdrawn as contaminated".
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import CursorResult, text  # noqa: E402


async def _list() -> int:
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT st.symbol, sg.classification, sg.confidence_pct,"
                    "       sg.created_at::date, sg.validity_until::date,"
                    "       sg.quarantined_at IS NOT NULL AS q, sg.quarantine_reason"
                    "  FROM signals sg JOIN stocks st ON st.id = sg.stock_id"
                    " ORDER BY sg.quarantined_at NULLS FIRST, sg.confidence_pct DESC"
                )
            )
        ).fetchall()
    if not rows:
        print("no signals")
        return 0
    q = sum(1 for r in rows if r.q)
    print(f"{len(rows)} signal(s); {q} quarantined, {len(rows) - q} live\n")
    for r in rows:
        mark = "⊘" if r.q else " "
        print(
            f" {mark} {r.symbol:<12} {r.classification:<11} {r.confidence_pct:>3}%  "
            f"minted {r[3]}  valid_to {r[4]}"
            + (f"  — {r.quarantine_reason}" if r.q else "")
        )
    return 0


async def _quarantine(before: date, reason: str, dry_run: bool) -> int:
    async with AsyncSessionFactory() as db:
        targets = (
            await db.execute(
                text(
                    "SELECT sg.id, st.symbol FROM signals sg JOIN stocks st ON st.id = sg.stock_id"
                    " WHERE sg.created_at < :d AND sg.quarantined_at IS NULL"
                    " ORDER BY st.symbol"
                ),
                {"d": datetime(before.year, before.month, before.day, tzinfo=UTC)},
            )
        ).fetchall()
        if not targets:
            print("nothing to quarantine")
            return 0
        print(f"{len(targets)} signal(s) would be withdrawn:")
        print("   " + ", ".join(r.symbol for r in targets))
        if dry_run:
            print("\ndry run — nothing written")
            return 0
        await db.execute(
            text(
                "UPDATE signals SET quarantined_at = now(), quarantine_reason = :why"
                " WHERE id = ANY(:ids)"
            ),
            {"why": reason[:255], "ids": [r.id for r in targets]},
        )
        await db.commit()
        print(f"\nwithdrawn {len(targets)} signal(s): {reason}")
    return 0


async def _release(signal_id: str) -> int:
    async with AsyncSessionFactory() as db:
        result = cast("CursorResult[Any]", await db.execute(
            text(
                "UPDATE signals SET quarantined_at = NULL, quarantine_reason = NULL"
                " WHERE id = :sid AND quarantined_at IS NOT NULL"
            ),
            {"sid": signal_id},
        ))
        await db.commit()
    if not result.rowcount:
        print(f"no quarantined signal with id {signal_id}", file=sys.stderr)
        return 1
    print(f"released {signal_id}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="withdraw signals without deleting them")
    p.add_argument("--list", action="store_true", help="show every signal and its state")
    p.add_argument("--before", type=date.fromisoformat, help="quarantine signals minted before")
    p.add_argument("--reason", type=str, help="why (stored verbatim, shown to the user)")
    p.add_argument("--release", type=str, help="lift the quarantine on one signal id")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.release:
        return asyncio.run(_release(args.release))
    if args.before:
        if not args.reason:
            p.error("--before requires --reason: an unexplained withdrawal is not reviewable")
        return asyncio.run(_quarantine(args.before, args.reason, args.dry_run))
    return asyncio.run(_list())


if __name__ == "__main__":
    raise SystemExit(main())
