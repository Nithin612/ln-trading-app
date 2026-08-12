#!/usr/bin/env python
"""Entry-quality attribution report (Phase 6 slice 6.2).

Writes docs/analysis/attribution-<date>.md — the per-cell expectancy table
(confidence · regime · direction · setup · time-of-day, marginals + a 2-D
slice) for the tradeable and shadow cohorts, with the n<20 no-rank affordance.
Read-only.

Usage:  cd backend && uv run python scripts/entry_attribution.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Runnable from any cwd: put backend/ (the `app` package root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.entry_attribution import (  # noqa: E402
    compute_attribution,
    render_attribution_markdown,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("entry_attribution")


async def _run() -> None:
    day = datetime.now(tz=UTC).date()
    async with AsyncSessionFactory() as db:
        tradeable = await compute_attribution(db, shadow=False)
        shadow = await compute_attribution(db, shadow=True)
    md = render_attribution_markdown([tradeable, shadow], day=day)
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"attribution-{day}.md"
    out.write_text(md)
    log.warning("wrote %s (tradeable n=%d, shadow n=%d)", out, tradeable.total, shadow.total)


if __name__ == "__main__":
    asyncio.run(_run())
