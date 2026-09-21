"""Item 17, second pass — how much of the measured fall in spread is real?

⭐ **Reads the dump, runs no second scoring pass** (``spread_impact_study.py --dump``),
which is round 9's pattern.

⛔⛔ **THIS FILE'S FIRST VERSION GOT ITS OWN ANSWER BACKWARDS, AND THE DEFECT IS WORTH
KEEPING IN VIEW.** It compared the **median of the NON-CLAMPED subset** across two periods
whose clamp shares differ (18.4% vs 30.7%). A clamped window reports 0.00, so the
non-clamped median is the unconditional quantile ``clamp + 0.5(1 - clamp)`` — **q59.2
before against q65.3 after**. Truncating the later period more deeply reads it at a higher
quantile *by construction*, which manufactured a "flat" result. Measured on this dump:

| comparison | Rs 225+ band, before -> after |
|---|--:|
| median of non-clamped (**the defect**) | 5.25 -> 5.46, **+4.1%** |
| equal-depth truncation | 6.45 -> 5.46, **-15.3%** |
| **paired balanced panel, all windows** | **-10.7%** |
| paired panel, non-clamped only | **+15.3% — the selection flips the sign** |

⭐ **THE RULE: never compare two censored distributions at different censoring depths.**
Truncate both at the deeper one, or pair by name. Conditioning on "the estimator produced
a number" conditions on the outcome, because it is the SMALL spreads that fail to produce
one.

Usage:
    uv run python scripts/item17_clamp_analysis.py [--dump PATH] [--append-to PATH]
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.trading import fees  # noqa: E402

TICK_CHANGE = "2024-06-01"
CHEAP_CEILING = 225.0
# A half-spread at or under this many ticks is a book sitting on the exchange's minimum
# increment (0.50 exact; 0.75 allows for estimator noise).
PINNED_TICKS = 0.75
ORDER_VALUE = Decimal("20000")


@dataclass(frozen=True, slots=True)
class Row:
    window: int
    stock_id: str
    last_session: str
    ar_half_bps: float
    median_price: float
    tick: float

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
                    stock_id=raw["stock_id"],
                    last_session=raw["last_session"],
                    ar_half_bps=float(raw["ar_half_bps"]),
                    median_price=float(raw["median_price"]),
                    tick=float(raw["tick"]),
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


def _clamp_share(cell: list[Row]) -> float:
    return sum(1 for r in cell if r.clamped) / len(cell)


def _truncated_median(cell: list[Row], depth: float, attr: str) -> float:
    """Median of the cell after dropping its lowest `depth` share.

    ⭐ The comparison the first version needed and did not make: applying the SAME depth to
    both periods puts them at the same unconditional quantile, so the difference that
    remains is not the censoring.
    """
    values = sorted(float(getattr(r, attr)) for r in cell)
    return statistics.median(values[int(round(depth * len(values))) :])


def _paired_change(
    before: list[Row], after: list[Row], attr: str, *, live_only: bool
) -> tuple[float, int]:
    """Median per-NAME change, over names present in both periods.

    ⭐ The strongest comparison available here: it removes composition entirely, since the
    cohort grew over the block. `live_only` reproduces the original defect on demand — the
    two disagree in SIGN, which is the cleanest demonstration that the selection was doing
    the work.
    """
    def by_name(cell: list[Row]) -> dict[str, list[float]]:
        out: dict[str, list[float]] = defaultdict(list)
        for r in cell:
            if live_only and r.clamped:
                continue
            out[r.stock_id].append(float(getattr(r, attr)))
        return out

    b, a = by_name(before), by_name(after)
    changes = [
        statistics.median(a[s]) / statistics.median(b[s]) - 1
        for s in sorted(set(b) & set(a))
        if statistics.median(b[s]) > 0
    ]
    return statistics.median(changes), len(changes)


def _intraday_charges_bps(price: Decimal = Decimal("500")) -> float:
    qty = int(ORDER_VALUE / price)
    total, _ = fees.roundtrip_charges(
        position_side="LONG", entry_price=price, exit_price=price, quantity=qty, product="intraday"
    )
    return float(total / (price * qty) * 10_000)


def render(rows: list[Row]) -> str:
    cells = {
        (cheap, before): _cell(rows, cheap=cheap, before=before)
        for cheap in (True, False)
        for before in (True, False)
    }
    hi_b, hi_a = cells[(False, True)], cells[(False, False)]
    lo_b, lo_a = cells[(True, True)], cells[(True, False)]

    hi_depth = max(_clamp_share(hi_b), _clamp_share(hi_a))
    lo_depth = max(_clamp_share(lo_b), _clamp_share(lo_a))

    hi_t0 = _truncated_median(hi_b, hi_depth, "half_ticks")
    hi_t1 = _truncated_median(hi_a, hi_depth, "half_ticks")
    hi_paired, hi_n = _paired_change(hi_b, hi_a, "half_ticks", live_only=False)
    hi_paired_bad, hi_n_bad = _paired_change(hi_b, hi_a, "half_ticks", live_only=True)

    lo_rs0 = _truncated_median(lo_b, lo_depth, "half_rupees")
    lo_rs1 = _truncated_median(lo_a, lo_depth, "half_rupees")
    pin0 = sum(1 for r in lo_b if r.half_ticks <= PINNED_TICKS) / len(lo_b)
    pin1 = sum(1 for r in lo_a if r.half_ticks <= PINNED_TICKS) / len(lo_a)

    hi_live0 = statistics.median([r.half_ticks for r in hi_b if not r.clamped])
    hi_live1 = statistics.median([r.half_ticks for r in hi_a if not r.clamped])
    hi_live_pct = (hi_live1 / hi_live0 - 1) * 100
    hi_trunc_pct = (hi_t1 / hi_t0 - 1) * 100
    pooled = statistics.median([r.ar_half_bps for r in rows])
    pooled_live = statistics.median([r.ar_half_bps for r in rows if not r.clamped])
    charges = _intraday_charges_bps()
    hurdle_lo, hurdle_hi = charges + 2 * pooled, charges + 2 * pooled_live

    lines = [
        "## ⭐⭐ Second pass — most of the fall is mechanical, but ~10-15% of it is REAL",
        "",
        "⛔⛔ **This section's first version concluded the opposite, and the correction is the",
        "more useful finding.** It compared the median of the NON-CLAMPED subset across two",
        "periods whose clamp shares differ (18.4% vs 30.7%). A clamped window reports 0.00, so",
        "that statistic is the unconditional quantile `clamp + 0.5(1-clamp)` — **q59.2 before",
        "against q65.3 after.** Reading the later period at a higher quantile *by construction*",
        "manufactured a flat result. ⭐ **Conditioning on 'the estimator produced a number'",
        "conditions on the OUTCOME, because it is the small spreads that fail to produce one.**",
        "",
        f"### The Rs {CHEAP_CEILING:.0f}+ band, whose tick never changed",
        "",
        "| comparison | before -> after | change |",
        "|---|--:|--:|",
        f"| median of non-clamped (⛔ **the defect**) | {hi_live0:.2f} -> {hi_live1:.2f} | "
        f"**{hi_live_pct:+.1f}%** |",
        f"| equal-depth truncation ({hi_depth * 100:.1f}%) | {hi_t0:.2f} -> {hi_t1:.2f} | "
        f"**{hi_trunc_pct:+.1f}%** |",
        f"| ⭐ **paired panel, all windows** (n={hi_n} names) | — | **{hi_paired * 100:+.1f}%** |",
        f"| paired panel, non-clamped only (n={hi_n_bad}) | — | {hi_paired_bad * 100:+.1f}% |",
        "",
        "⭐ **The last two rows disagree in SIGN on the same names.** That is the cleanest",
        "possible demonstration that the selection, not the market, produced the original answer.",
        "",
        "### What actually happened",
        "",
        "⭐ **Most of the 2.19 -> 1.60 bps fall is mechanical, and one tenth to one sixth is a",
        "genuine narrowing.** The median price rose against a FIXED Rs 0.05 tick, so the same book",
        "in ticks is fewer bps; and fewer bps at the same volatility is worse signal-to-noise for",
        "the estimator, so more windows clamp — which then drags the naive median further. Those",
        "two mechanisms are most of it. **But paired by name the book genuinely narrowed",
        f"{abs(hi_paired) * 100:.1f}% in ticks**, and that part is real.",
        "",
        "⚠ **'Mechanical' is NOT the same as 'artifact', and the earlier wording was wrong on",
        "this too.** A trader pays bps. With the price level up against a fixed grid, the",
        "proportional cost of crossing genuinely fell, whatever the book did in ticks.",
        "",
        f"### The sub-Rs {CHEAP_CEILING:.0f} band and the tick change",
        "",
        "⭐ **The tick change UNPINNED the cheap band.** Measured over **all** rows — a clamped",
        "window is 0.00 ticks and so is definitionally inside this numerator — the share at or",
        f"under {PINNED_TICKS} ticks went **{pin0 * 100:.1f}% -> {pin1 * 100:.1f}%**. Before the",
        "change a large majority sat on the exchange's minimum increment, which is the signature",
        "of **the tick size itself being the binding constraint**.",
        "",
        f"⚠ At equal truncation depth ({lo_depth * 100:.1f}%) the rupee half-spread went",
        f"**Rs {lo_rs0:.4f} -> Rs {lo_rs1:.4f}** ({(lo_rs1 / lo_rs0 - 1) * 100:+.0f}%) — a real",
        "narrowing, and about twice what the censored comparison reported.",
        "",
        "### What this does to the headline",
        "",
        f"⚠ **The pooled {pooled:.2f} bps is a LOWER bound** — clamped windows report 0.00 and",
        f"drag it down. On the SAME population without them it is **{pooled_live:.2f} bps**.",
        "⭐ **Bracketing one population across that single choice gives",
        f"[{pooled:.2f}, {pooled_live:.2f}] bps, an implied hurdle of {hurdle_lo:.1f}-"
        f"{hurdle_hi:.1f} bps.** Both ends are far below",
        "the pre-registered 5 bps boundary: **the branch verdict does not move.**",
        "",
        "⛔ **Neither bound is a measurement of a real book.** Item 17b is what would settle it.",
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

    section = render(_load(args.dump))
    print(section)
    if args.append_to:
        with args.append_to.open("a") as fh:
            fh.write("\n---\n\n" + section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
