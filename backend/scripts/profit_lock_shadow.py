"""Profit-lock shadow report — replay exit policies over closed paper trades.

Usage:
    uv run python scripts/profit_lock_shadow.py [--limit 30]

Read-only. Prints, per closed position with a 1m tape, the max favourable
excursion (peak gross profit), the ACTUAL realised result and capture %, and
what each candidate policy (current ladder vs Layered Ratchet Stop vs a plain
33% giveback) WOULD have realised and captured. This is the evidence layer for
the Dynamic Profit Lock — it drives no live orders. See
app/services/profit_lock_shadow.py.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# Runnable from any cwd: backend/ (the `app` package root) onto sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.trading import Position  # noqa: E402
from app.services.profit_lock_shadow import compare_position  # noqa: E402
from sqlalchemy import select  # noqa: E402


def _pct(x: float | None) -> str:
    return f"{x * 100:5.0f}%" if x is not None else "   — "


def _money(x: Decimal | None) -> str:
    return f"{float(x):>10,.0f}" if x is not None else "         —"


async def run(limit: int) -> int:
    now = datetime.now(tz=UTC)
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                select(Position)
                .where(Position.mode == "paper", Position.closed_at.is_not(None))
                .order_by(Position.closed_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        if not rows:
            print("No closed paper positions.", flush=True)
            return 0

        for pos in rows:
            comp = await compare_position(db, pos, now=now)
            head = f"{comp.symbol:<12} {comp.side:<5} {comp.classification:<10} qty={comp.quantity}"
            if comp.note:
                print(f"{head}   [{comp.note}]", flush=True)
                continue
            print(
                f"\n{head}\n"
                f"  peak(gross) {_money(comp.peak_gross)}   "
                f"actual(net) {_money(comp.actual_net)}   "
                f"capture {_pct(comp.actual_capture_pct)}   bars={comp.bars}",
                flush=True,
            )
            print(f"  {'policy':<14}{'exit':>10}{'net':>12}{'capture':>10}  ", flush=True)
            for p in comp.policies:
                flag = " (open@end)" if p.still_open else ""
                exitpx = f"{float(p.exit_price):,.2f}" if p.exit_price is not None else "—"
                print(
                    f"  {p.policy:<14}{exitpx:>10}{_money(p.exit_net)}{_pct(p.capture_pct)}{flag}",
                    flush=True,
                )
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Profit-lock shadow report")
    ap.add_argument("--limit", type=int, default=30, help="most recent N closed trades")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args.limit)))


if __name__ == "__main__":
    main()
