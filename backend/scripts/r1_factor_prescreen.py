"""R1 pre-screen — do VWAP / RVOL relate to our outcomes at all, BEFORE touching the engine?

    uv run python scripts/r1_factor_prescreen.py

## Why this runs first

R1 proposes VWAP and RVOL as new confluence factors. That is **frozen-engine** work, and the
real cost is not the Python function — it is:

    Python factor  +  a byte-identical Rust factor (`engine-core/src/factors.rs`)
    +  7 golden fixtures regenerated  +  EXACT parity on scores/confidence/decisions
    +  an §8 backtest regression  +  a hook-protected SIGNAL_ENGINE.md spec change

Days of work. So the cheap question comes first: **on the trades we actually took, does
either quantity separate winners from losers?** If not, the expensive change is answered
without paying for it.

## Two findings that reshape the proposal

⭐ **1. RVOL already exists in the engine.** `app/analysis/indicators/volume.py` computes
`ratio = current_volume / 20-period average` — that *is* relative volume. It is simply
**binarised**: `+0.5` when `ratio >= 1.5`, `0.0` otherwise. So "add RVOL" is really *"grade
the existing binary"*, which is a change to one scoring function rather than a new factor.
This script therefore tests the **graded** quantity: does the ratio's *magnitude* carry
information the 1.5 threshold throws away?

⭐ **2. VWAP is an intraday construct.** Session VWAP does not exist on a daily candle. What
works on daily bars is **anchored VWAP** — volume-weighted average price from a chosen
anchor. That anchor is a *spec decision*, not an implementation detail. Here we use a
20-day anchor as a stand-in and label it as such.

⚠ **Read-only. The frozen engine is untouched.** This measures; it does not change scoring.
⚠ **No look-ahead:** both quantities are computed from bars strictly BEFORE the entry date.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

#: Mirrors `app/analysis/indicators/volume.py` exactly, so the comparison is against the
#: engine's own definition rather than a lookalike.
_AVG_PERIOD = 20
_LIVE_THRESHOLD = 1.5

_POSITIONS = text(
    """
    SELECT p.stock_id, s.symbol, p.opened_at::date AS entry_date, p.side,
           p.realized_pnl,
           (p.realized_pnl / NULLIF(p.quantity * p.avg_entry_price, 0)) AS ret
    FROM positions p JOIN stocks s ON s.id = p.stock_id
    WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
    """
)

#: STRICTLY BEFORE the entry date (constraint #3).
_BARS = text(
    """
    SELECT close, volume FROM ohlcv_1d
    WHERE stock_id = :sid AND time::date < :entry
    ORDER BY time DESC LIMIT 40
    """
)


@dataclass
class Row:
    symbol: str
    entry: date
    ret: float
    pnl: float
    rvol: float
    vwap_gap: float  # (close − anchored VWAP) / VWAP, in %


def _quintiles(rows: list[Row], key: Callable[[Row], float]) -> list[list[Row]]:
    o = sorted(rows, key=key)
    n = len(o) // 5
    return [o[q * n : (q + 1) * n] if q < 4 else o[4 * n :] for q in range(5)]


def _line(i: int, b: list[Row], label: float, unit: str) -> str:
    mr = statistics.fmean(r.ret for r in b) * 100
    w = sum(1 for r in b if r.pnl > 0)
    return (
        f"| Q{i} | {len(b)} | {label:,.2f}{unit} | {mr:+.3f}% | "
        f"{100 * w / len(b):.0f}% | ₹{sum(r.pnl for r in b):,.0f} |"
    )


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        positions = list((await db.execute(_POSITIONS)).all())
        rows: list[Row] = []
        skipped = 0
        for p in positions:
            if p.ret is None:
                skipped += 1
                continue
            bars = list(
                (await db.execute(_BARS, {"sid": p.stock_id, "entry": p.entry_date})).all()
            )
            if len(bars) < _AVG_PERIOD + 1:
                skipped += 1
                continue
            closes = [float(b.close) for b in bars]
            vols = [float(b.volume) for b in bars]
            avg = statistics.fmean(vols[1 : _AVG_PERIOD + 1])
            if avg <= 0:
                skipped += 1
                continue
            rvol = vols[0] / avg
            tv = sum(c * v for c, v in zip(closes[:20], vols[:20], strict=True))
            vv = sum(vols[:20])
            if vv <= 0:
                skipped += 1
                continue
            vwap = tv / vv
            rows.append(
                Row(
                    symbol=p.symbol, entry=p.entry_date, ret=float(p.ret),
                    pnl=float(p.realized_pnl), rvol=rvol,
                    vwap_gap=100.0 * (closes[0] - vwap) / vwap,
                )
            )

    if len(rows) < 25:
        print(f"only {len(rows)} evaluable positions — too few to quintile")
        return 1

    by_rvol = _quintiles(rows, lambda r: r.rvol)
    by_vwap = _quintiles(rows, lambda r: r.vwap_gap)
    fired = [r for r in rows if r.rvol >= _LIVE_THRESHOLD]
    quiet = [r for r in rows if r.rvol < _LIVE_THRESHOLD]

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# R1 pre-screen — do VWAP / RVOL separate our outcomes? ({now.date().isoformat()})",
        "",
        "**Run before the frozen-engine work, not after.** Adding a confluence factor costs a",
        "Python impl **plus a byte-identical Rust impl**, 7 regenerated golden fixtures, exact",
        "parity on scores/confidence/decisions, an §8 regression and a hook-protected spec",
        "change. Days. So first: does either quantity separate winners from losers on the",
        f"trades we actually took? **{len(rows)} closed positions** ({skipped} skipped for",
        "insufficient history).",
        "",
        "⚠ No look-ahead — both computed from bars strictly BEFORE the entry date.",
        "",
        "## 1. RVOL (graded) — the factor that already exists",
        "",
        "⭐ `volume_factor` already computes `current / 20-day average`. It is **binarised** at",
        f"`>= {_LIVE_THRESHOLD}` → `+0.5`, else `0.0`. So the real R1 question is whether the",
        "**magnitude** carries information the threshold discards.",
        "",
        "| quintile | n | mean RVOL | mean return | win | total |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    out += [
        _line(i, b, statistics.fmean(r.rvol for r in b), "×")
        for i, b in enumerate(by_rvol, start=1)
    ]

    out += [
        "",
        "### And how the LIVE binary threshold actually splits",
        "",
        "| cohort | n | mean return | win | total |",
        "|---|--:|--:|--:|--:|",
    ]
    for label, grp in (("RVOL ≥ 1.5 (factor fires)", fired), ("RVOL < 1.5 (silent)", quiet)):
        if grp:
            out.append(
                f"| {label} | {len(grp)} | "
                f"{statistics.fmean(r.ret for r in grp) * 100:+.3f}% | "
                f"{100 * sum(1 for r in grp if r.pnl > 0) / len(grp):.0f}% | "
                f"₹{sum(r.pnl for r in grp):,.0f} |"
            )

    out += [
        "",
        "## 2. Anchored VWAP gap — price vs its own 20-day volume-weighted average",
        "",
        "⚠ **The anchor is a stand-in.** Session VWAP does not exist on daily bars; a real",
        "anchored VWAP would run from a swing pivot, and *choosing that anchor is a spec",
        "decision*. A 20-day anchor is used here to get a first read.",
        "",
        "| quintile | n | mean gap | mean return | win | total |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    out += [
        _line(i, b, statistics.fmean(r.vwap_gap for r in b), "%")
        for i, b in enumerate(by_vwap, start=1)
    ]

    r_lo = statistics.fmean(r.ret for r in by_rvol[0])
    r_hi = statistics.fmean(r.ret for r in by_rvol[4])
    v_lo = statistics.fmean(r.ret for r in by_vwap[0])
    v_hi = statistics.fmean(r.ret for r in by_vwap[4])

    out += [
        "",
        "## Verdict",
        "",
        f"- **RVOL** Q5−Q1 spread: **{(r_hi - r_lo) * 100:+.3f} pp**",
        f"- **VWAP gap** Q5−Q1 spread: **{(v_hi - v_lo) * 100:+.3f} pp**",
        "",
        "⚠ **n ≈ 21 per quintile.** Nothing here approaches the t ≈ 3.6 bar, and that bar does",
        "not fall with more data. This is a **screen**, not a test: it exists to decide whether",
        "the expensive engine change is worth starting, not to promote anything.",
        "",
        "**How to read it:** a monotonic gradient with a wide spread would justify the frozen-",
        "engine work. A flat or non-monotonic one says the factor carries nothing our existing",
        "confluence does not already have — and the fixtures, parity work and spec change",
        "should not be spent.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"r1-factor-prescreen-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
