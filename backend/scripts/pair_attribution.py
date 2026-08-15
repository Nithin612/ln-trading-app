#!/usr/bin/env python
"""Pair-attribution report (Phase 6.5b slice 4) — shadow pair expectancy (df-vs-adf verdict)
→ docs/analysis/pair-attribution-<date>.md. Read-only.

Usage:  cd backend && uv run python scripts/pair_attribution.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import pair_attribution as pa  # noqa: E402

log = logging.getLogger("pair_attribution")


async def main() -> None:
    logging.disable(logging.INFO)
    async with AsyncSessionFactory() as db:
        attr = await pa.compute_pair_attribution(db)
    day = datetime.now(tz=UTC).date()
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"pair-attribution-{day}.md"
    out.write_text(pa.render_markdown(attr, day=day))
    print(f"wrote {out} — {attr.total} resolved shadow pair signal(s)")


if __name__ == "__main__":
    asyncio.run(main())
