#!/usr/bin/env python
"""Corpus-scale entry-quality attribution (Phase 6 slice 6.2b).

Runs the parity-clean Rust backtest (tradecore.run_universe) over the Nifty50
daily corpus and writes docs/analysis/attribution-corpus-<date>.md — the same
per-cell expectancy table as the live report, but with statistical power.
Read-only; the frozen engine is untouched.

Usage:  cd backend && uv run python scripts/corpus_attribution.py
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
from app.services.corpus_attribution import compute_corpus_attribution  # noqa: E402
from app.services.entry_attribution import render_attribution_markdown  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("corpus_attribution")


async def _run() -> None:
    day = datetime.now(tz=UTC).date()
    async with AsyncSessionFactory() as db:
        rep = await compute_corpus_attribution(db)
    md = render_attribution_markdown([rep], day=day)
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"attribution-corpus-{day}.md"
    out.write_text(md)
    log.warning("wrote %s (corpus trades=%d)", out, rep.total)


if __name__ == "__main__":
    asyncio.run(_run())
