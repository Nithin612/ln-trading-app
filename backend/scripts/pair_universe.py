#!/usr/bin/env python
"""Pair-trading universe screen (Phase 6.5a.2). Screen same-sector Nifty50 pairs for
tradeable mean-reversion candidates and write docs/analysis/pairs-<date>.md.

Read-only research artifact — mints NO signal (shadow-first; frozen engine untouched).

Usage:  cd backend && uv run python scripts/pair_universe.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import pair_universe as pu  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pair_universe")


async def main() -> None:
    # The app engine enables SQL echo at import; this is a read-only CLI, so silence
    # INFO and below — stdout is then just the ranked candidates + the "wrote …" line.
    logging.disable(logging.INFO)
    async with AsyncSessionFactory() as db:
        df = await pu.screen_universe(db, method="df")
        adf = await pu.screen_universe(db, method="adf")

    df_set = {(c.symbol_a, c.symbol_b) for c in df}
    adf_set = {(c.symbol_a, c.symbol_b) for c in adf}
    day = datetime.now(tz=UTC).date()
    print(f"df: {len(df)} candidates · adf: {len(adf)} · both: {len(df_set & adf_set)}")
    print(
        f"adf-only (wider net, awaits forward validation): {len(adf_set - df_set)} · "
        f"df-only (adf missed): {len(df_set - adf_set)}\n"
    )
    print(f"{'pair':<22}{'sector':<20}{'half-life':>10}{'DF t':>8}{'z now':>8}")
    for c in df[:25]:
        s = c.stat
        print(
            f"{c.symbol_a + '-' + c.symbol_b:<22}{(c.sector or '')[:19]:<20}"
            f"{s.half_life:>10.1f}{s.df_tstat:>8.2f}{s.zscore:>+8.2f}"
        )

    # The conservative df method is the report of record; adf is the wider-net cross-check
    # (its extra pairs await forward shadow validation — see phase-06-6.5-pairtrading-plan.md).
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"pairs-{day}.md"
    out.write_text(pu.render_markdown(df, day=day, method="df"))
    log.warning("wrote %s (df method; %d candidates)", out, len(df))


if __name__ == "__main__":
    asyncio.run(main())
