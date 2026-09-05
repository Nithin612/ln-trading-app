#!/usr/bin/env python
"""Gate experiment (Phase 6): does raising the confluence gate and/or skipping the
transitional ADX regime improve the backtest? A read-only comparison over the
Nifty50 daily corpus (Rust `run_universe`) — NO engine change; it tests the 6.2
verdict before any engine change is even proposed.

Four variants isolate each lever:
  gate-70 (baseline) · gate-80 · gate-70 + skip-transitional · gate-80 + skip-transitional

Metrics: trades · decided · win% · mean expectancy_r (winsorized) · total-R
(Σ realized R — the net-profit proxy) · reach-1R. Prints a table and writes
docs/analysis/gate-experiment-<date>.md.

Usage:  cd backend && uv run python scripts/gate_experiment.py
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Runnable from any cwd: put backend/ (the `app` package root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ratios import WINSOR_R  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.corpus_attribution import corpus_rows  # noqa: E402
from app.services.entry_attribution import Row, _regime_bucket, realized_r  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gate_experiment")

_TRANSITIONAL = "transitional (20–25)"


@dataclass
class Agg:
    trades: int
    decided: int
    win_rate: float | None
    mean_exp_r: float | None
    total_r: float
    reach_1r: float | None


def _aggregate(rows: list[Row]) -> Agg:
    decided = [r for r in rows if r.status in ("tp_first", "sl_first")]
    wins = sum(1 for r in decided if r.status == "tp_first")
    exp = [r for r in (realized_r(d) for d in decided) if r is not None]
    mfes = [r.mfe_r for r in rows if r.mfe_r is not None]
    reached = sum(1 for r in rows if r.mfe_r is not None and r.mfe_r >= 1.0)
    return Agg(
        trades=len(rows),
        decided=len(decided),
        win_rate=(wins / len(decided)) if decided else None,
        mean_exp_r=statistics.fmean(exp) if exp else None,
        total_r=sum(exp),
        reach_1r=(reached / len(mfes)) if mfes else None,
    )


def _skip_transitional(rows: list[Row]) -> list[Row]:
    return [r for r in rows if _regime_bucket(r.adx) != _TRANSITIONAL]


def _cells(name: str, a: Agg) -> tuple[str, str, str, str, str, str, str]:
    wr = f"{a.win_rate:.0%}" if a.win_rate is not None else "—"
    me = f"{a.mean_exp_r:+.3f}" if a.mean_exp_r is not None else "—"
    r1 = f"{a.reach_1r:.0%}" if a.reach_1r is not None else "—"
    return (name, str(a.trades), str(a.decided), wr, me, f"{a.total_r:+.1f}", r1)


async def main() -> None:
    async with AsyncSessionFactory() as db:
        g70 = await corpus_rows(db, min_confidence=70)
        g80 = await corpus_rows(db, min_confidence=80)
    variants = [
        ("gate-70 (baseline)", g70),
        ("gate-80", g80),
        ("gate-70 + skip transitional", _skip_transitional(g70)),
        ("gate-80 + skip transitional", _skip_transitional(g80)),
    ]
    header = ("variant", "trades", "decided", "win%", "mean expR", "total-R", "reach1R")
    rows = [_cells(name, _aggregate(r)) for name, r in variants]

    # console (aligned)
    w = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(len(header))]
    def line(c: tuple[str, ...]) -> str:
        return "  ".join(c[i].ljust(w[i]) if i == 0 else c[i].rjust(w[i]) for i in range(len(c)))
    print(line(header))
    for r in rows:
        print(line(r))

    # markdown
    day = datetime.now(tz=UTC).date()
    md = [
        f"# Gate experiment — {day}",
        "",
        "_Read-only backtest over the Nifty50 daily corpus (Rust `run_universe`); NO "
        "engine change. `mean expR` = mean over decided of (+RR/−1R), winsorized "
        f"±{WINSOR_R:.0f}R; `total-R` = Σ realized R (net-profit proxy); `reach1R` = "
        "share whose MFE reached +1R._",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" + "--:|" * (len(header) - 1),
        *["| " + " | ".join(r) + " |" for r in rows],
    ]
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"gate-experiment-{day}.md"
    out.write_text("\n".join(md) + "\n")
    log.warning("wrote %s", out)


if __name__ == "__main__":
    asyncio.run(main())
