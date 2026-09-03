#!/usr/bin/env python
"""Regime-gate shadow measurement (Phase 6). What the regime-eligibility overlay
WOULD do to the LIVE tradeable cohort — the forward, live counterpart to the §8
backtest. Read-only; suppresses nothing (the overlay defaults to shadow mode).

Usage:  cd backend && uv run python scripts/regime_gate_shadow.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import regime_gate_shadow as rgs  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("regime_gate_shadow")


async def main() -> None:
    async with AsyncSessionFactory() as db:
        result = await rgs.compute_regime_gate_shadow(db)

    b, g, k = result.baseline, result.gated, result.killed
    print(f"live cohort: {b.trades} signals, skip={sorted(result.skip)}\n")
    print(f"{'variant':<28}{'trades':>8}{'win%':>7}{'expR':>9}{'total-R':>9}")
    for name, m in (("baseline", b), ("gated (kept)", g), ("killed (suppressed)", k)):
        wr = f"{m.win_rate:.0%}" if m.win_rate is not None else "—"
        er = f"{m.mean_exp_r:+.3f}" if m.mean_exp_r is not None else "—"
        print(f"{name:<28}{m.trades:>8}{wr:>7}{er:>9}{m.total_r:>+9.1f}")

    day = datetime.now(tz=UTC).date()
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"regime-gate-shadow-{day}.md"
    out.write_text(rgs.render_markdown(result, day=day, mode=settings.regime_gate_mode))
    log.warning("wrote %s", out)


if __name__ == "__main__":
    asyncio.run(main())
