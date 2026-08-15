#!/usr/bin/env python
"""Mint shadow pair signals (Phase 6.5b slice 2) — run the screen (df + adf arms) and
mint a SHADOW PairSignal for every currently-extreme (|z| ≥ entry) candidate. Writes only
to `pair_signals` (never tradeable). De-duped against open signals, so safe to re-run.

Usage:  cd backend && uv run python scripts/pair_minter.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from app.services.pair_minter import mint_pair_signals  # noqa: E402
from sqlalchemy import select  # noqa: E402

log = logging.getLogger("pair_minter")


async def main() -> None:
    logging.disable(logging.INFO)
    async with AsyncSessionFactory() as db:
        minted = await mint_pair_signals(db)
        ids = {sid for s in minted for sid in (s.stock_a_id, s.stock_b_id)}
        sym = (
            {
                i: n
                for i, n in (
                    await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(ids)))
                ).all()
            }
            if ids
            else {}
        )
    print(f"minted {len(minted)} shadow pair signal(s) (df+adf arms):")
    for s in minted:
        print(
            f"  {s.method:<4} {s.direction:<12} "
            f"{sym.get(s.stock_a_id, s.stock_a_id)}-{sym.get(s.stock_b_id, s.stock_b_id)} "
            f"z={s.entry_z:+.2f} half-life={s.half_life:.1f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
