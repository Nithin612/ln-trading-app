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
        candidates = await pu.screen_universe(db)

    day = datetime.now(tz=UTC).date()
    print(f"screened same-sector Nifty50 pairs → {len(candidates)} candidate(s)\n")
    print(f"{'pair':<24}{'sector':<20}{'half-life':>10}{'DF t':>8}{'z now':>8}")
    for c in candidates[:25]:
        s = c.stat
        print(
            f"{c.symbol_a + '-' + c.symbol_b:<24}{(c.sector or '')[:19]:<20}"
            f"{s.half_life:>10.1f}{s.df_tstat:>8.2f}{s.zscore:>+8.2f}"
        )

    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"pairs-{day}.md"
    out.write_text(pu.render_markdown(candidates, day=day))
    log.warning("wrote %s", out)


if __name__ == "__main__":
    asyncio.run(main())
