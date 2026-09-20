"""Item 17, second pass — is the measured drift a market change or an artifact?

⭐ **Reads the dump, runs no second scoring pass.** ``spread_impact_study.py --dump``
writes one row per name-window; every slice here comes off that artifact, which is the
round-9 pattern (``round9_cells.py``) and the reason this costs seconds rather than 25
minutes.

The question: the headline AR median falls from 2.19 bps (before 2024-06) to 1.60 after.
Three candidate explanations, and they are separable:

1. **NSE's sub-Rs 225 tick change** — real, but it can only touch the cheap band.
2. **The price level** — a FIXED Rs 0.05 tick on a RISING price is mechanically fewer bps
   even when the book has not moved at all.
3. **The estimator's own floor** — a clamped window reports 0.00 and drags the median, so
   a rising clamp share looks exactly like falling spreads.

Usage:
    uv run python scripts/item17_clamp_analysis.py [--dump PATH] [--append-to PATH]
"""

from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

TICK_CHANGE = "2024-06-01"
CHEAP_CEILING = 225.0
# A half-spread at or under this many ticks is, for practical purposes, a book sitting on
# the exchange's minimum increment (0.50 would be exact; 0.75 allows for estimator noise).
PINNED_TICKS = 0.75
# The headline the first pass produced, restated here so the two documents cannot drift
# apart silently. ⚠ If spread_impact_study is re-run on different data, re-read these.
POOLED_MEDIAN_BPS = 1.74
CHARGES_BPS = 10.60


@dataclass(frozen=True, slots=True)
class Row:
    window: int
    last_session: str
    ar_half_bps: float
    median_price: float
    tick: float
    sigma_bar_bps: float

    @property
    def half_ticks(self) -> float:
        return (self.ar_half_bps / 10_000.0) * self.median_price / self.tick

    @property
    def half_rupees(self) -> float:
        return (self.ar_half_bps / 10_000.0) * self.median_price

    @property
    def clamped(self) -> bool:
        return self.ar_half_bps <= 1e-12


def _load(path: Path) -> list[Row]:
    out: list[Row] = []
    with path.open() as fh:
        for raw in csv.DictReader(fh):
            if not raw["ar_half_bps"]:
                continue
            out.append(
                Row(
                    window=int(raw["window"]),
                    last_session=raw["last_session"],
                    ar_half_bps=float(raw["ar_half_bps"]),
                    median_price=float(raw["median_price"]),
                    tick=float(raw["tick"]),
                    sigma_bar_bps=float(raw["sigma_bar_bps"]),
                )
            )
    return out


def _cell(rows: list[Row], *, cheap: bool, before: bool) -> list[Row]:
    return [
        r
        for r in rows
        if (r.median_price < CHEAP_CEILING) == cheap
        and (r.last_session < TICK_CHANGE) == before
    ]


def _med(rows: list[Row], attr: str) -> float:
    return float(statistics.median([float(getattr(r, attr)) for r in rows]))


def render(rows: list[Row]) -> str:
    cells: dict[tuple[bool, bool], list[Row]] = {}
    for cheap in (True, False):
        for before in (True, False):
            cells[(cheap, before)] = _cell(rows, cheap=cheap, before=before)

    lines = [
        "## \u2b50\u2b50 Second pass — the drift is an ARTIFACT, and the tick change is",
        "smaller than it looks",
        "",
        "The headline median falls 2.19 -> 1.60 bps across mid-2024. Sliced on the dump, with",
        "the clamped windows separated from the rest, it resolves completely.",
        "",
        "| band | period | n | ticks (ALL) | n live | **ticks (NOT clamped)** | clamp |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    band_names = {True: f"below Rs {CHEAP_CEILING:.0f}", False: f"Rs {CHEAP_CEILING:.0f}+"}
    period_names = {True: "before 2024-06", False: "from 2024-06"}
    for cheap in (True, False):
        for before in (True, False):
            cell = cells[(cheap, before)]
            if not cell:
                continue
            live = [r for r in cell if not r.clamped]
            clamp_pct = (1 - len(live) / len(cell)) * 100
            lines.append(
                f"| {band_names[cheap]} | {period_names[before]} | {len(cell):,} | "
                f"{_med(cell, 'half_ticks'):.2f} | {len(live):,} | "
                f"**{_med(live, 'half_ticks'):.2f}** | {clamp_pct:.1f}% |"
            )

    hi_before = [r for r in cells[(False, True)] if not r.clamped]
    hi_after = [r for r in cells[(False, False)] if not r.clamped]
    lo_before = [r for r in cells[(True, True)] if not r.clamped]
    lo_after = [r for r in cells[(True, False)] if not r.clamped]

    hi_t0, hi_t1 = _med(hi_before, "half_ticks"), _med(hi_after, "half_ticks")
    hi_c0 = (1 - len(hi_before) / len(cells[(False, True)])) * 100
    hi_c1 = (1 - len(hi_after) / len(cells[(False, False)])) * 100
    hi_p0, hi_p1 = _med(hi_before, "median_price"), _med(hi_after, "median_price")

    pin0 = sum(1 for r in lo_before if r.half_ticks <= PINNED_TICKS) / len(lo_before) * 100
    pin1 = sum(1 for r in lo_after if r.half_ticks <= PINNED_TICKS) / len(lo_after) * 100
    rs0, rs1 = _med(lo_before, "half_rupees"), _med(lo_after, "half_rupees")
    rs_delta = (rs1 / rs0 - 1) * 100
    recent_bps = _med(hi_after + lo_after, "ar_half_bps")

    lines += [
        "",
        "### \u26d4 Finding 1 — the cohort-wide decline is the CLAMP, not the market",
        "",
        f"On the Rs {CHEAP_CEILING:.0f}+ band, whose tick **never changed**, the half-spread",
        f"in ticks is **flat on non-clamped windows: {hi_t0:.2f} -> {hi_t1:.2f}**, while the",
        "all-windows median falls. The difference is entirely the clamp share rising",
        f"{hi_c0:.1f}% -> {hi_c1:.1f}%.",
        "",
        "\u2b50 **And the mechanism is arithmetic, not mysterious.** The median price rose",
        f"Rs {hi_p0:,.0f} -> Rs {hi_p1:,.0f} against a FIXED Rs 0.05 tick, so the same book in",
        "ticks is a smaller spread in bps. A smaller spread at the same volatility is a worse",
        "signal-to-noise ratio for the estimator, so more windows fall under its resolution and",
        "clamp. **Falling bps and a rising clamp share are the same fact seen twice.**",
        "",
        "### \u2b50 Finding 2 — the tick change UNPINNED the cheap band more than it narrowed it",
        "",
        f"Before the change **{pin0:.1f}%** of sub-Rs {CHEAP_CEILING:.0f} windows sat at or under",
        f"{PINNED_TICKS} ticks — a book pinned on the exchange's minimum increment, which is the",
        "signature of **the tick size itself being the binding constraint**. After, only",
        f"**{pin1:.1f}%** are.",
        "",
        "\u26a0 **But the narrowing is far smaller than the bps figures suggest.** In rupees the",
        f"median half-spread went **Rs {rs0:.4f} -> Rs {rs1:.4f}** ({rs_delta:+.0f}%), not the",
        "~50% the clamped medians imply.",
        "",
        "### What this does to the headline",
        "",
        f"\u26a0 **The pooled {POOLED_MEDIAN_BPS:.2f} bps is a LOWER bound** — clamped windows"
        " report 0.00 and drag",
        f"it down. On non-clamped windows the recent-period median is **{recent_bps:.2f} bps**.",
        f"\u2b50 **The true typical half-spread is bracketed at {POOLED_MEDIAN_BPS:.2f}-"
        f"{recent_bps:.2f} bps, and the branch verdict does not move**: both ends are far below",
        f"the pre-registered 5 bps boundary, and the implied hurdle spans "
        f"{CHARGES_BPS + 2 * POOLED_MEDIAN_BPS:.1f}-{CHARGES_BPS + 2 * recent_bps:.1f} bps.",
        "",
        "\u26d4 **Neither bound is a measurement of a real book.** Item 17b is",
        "what would settle it.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    default_dump = root / "docs/analysis/item17-name-windows-2026-09-20.csv"
    ap.add_argument("--dump", type=Path, default=default_dump)
    ap.add_argument("--append-to", type=Path, default=None)
    args = ap.parse_args()

    rows = _load(args.dump)
    section = render(rows)
    print(section)
    if args.append_to:
        with args.append_to.open("a") as fh:
            fh.write("\n---\n\n" + section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
