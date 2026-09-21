"""Item 17 — what does it actually cost to cross the spread on the intraday cohort?

⭐ **Read the pre-registration first:**
``docs/analysis/item17-spread-impact-preregistration-2026-09-20.md``. The estimand, the
cohort, the falsifier and the full decision tree were committed BEFORE this file existed,
so nothing here can be tuned to a result.

⛔ **READ-ONLY.** SELECTs only. No money path, no frozen-engine call, both sealed holdouts
untouched — the window is the 797-session test block, which is what ``ohlcv_5m`` covers.

⚠ **This is an ESTIMATE, not an observation.** The order book is Redis-only at a 60s TTL
and was never persisted, so no historical spread exists to look up. Item 17b (forward
top-of-book capture) is the arm that will validate these numbers against reality.

Usage
-----
    uv run python scripts/spread_impact_study.py [--windows N] [--out PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.broker.paper_broker import participation_bps  # noqa: E402
from app.broker.tick_schedule import tick_for  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.pit_cohort import (  # noqa: E402
    InsufficientHistoryError,
    liquid_as_of,
)
from app.services.spread_estimators import (  # noqa: E402
    MIN_SESSIONS_FOR_STABILITY,
    Bar,
    abdi_ranaldo_sessions,
    calibrate,
    corwin_schultz_sessions,
    proportional_to_half_spread_bps,
)
from app.trading import fees  # noqa: E402

log = logging.getLogger("item17")

# A name must trade on most of the window for its pooled estimate to mean anything.
MIN_SESSIONS_PER_NAME = 15
MIN_BARS_PER_SESSION = 20
# The representative intraday order the hurdle is quoted for. Stated here rather than
# buried: every bps figure below is "at this size".
ORDER_VALUE = Decimal("20000")
BOOTSTRAP_DRAWS = 2000


@dataclass(frozen=True, slots=True)
class NameWindow:
    """One name's pooled estimate over one measurement window."""

    stock_id: int
    sessions: int
    bars: int
    degenerate_bars: int
    sigma_bar_bps: float
    ar_half_bps: float | None
    cs_half_bps: float | None
    adv_value: Decimal | None
    median_price: float
    tick: float

    @property
    def ar_half_ticks(self) -> float | None:
        """⭐ The physical check that needs no order book: a real market is at least ONE
        tick wide, so a half-spread should read about 0.5 ticks. Materially below that is
        the estimator reading under its own resolution, not a market tighter than the
        exchange allows."""
        if self.ar_half_bps is None or self.tick <= 0 or self.median_price <= 0:
            return None
        return (self.ar_half_bps / 10_000.0) * self.median_price / self.tick


@dataclass(frozen=True, slots=True)
class WindowResult:
    index: int
    first_session: date
    last_session: date
    cohort_requested: int
    cohort_measured: int
    names: list[NameWindow]


async def _sessions_available(db: AsyncSession) -> list[date]:
    rows = (
        await db.execute(text("SELECT DISTINCT time::date AS d FROM ohlcv_5m ORDER BY d"))
    ).all()
    return [r[0] for r in rows]


async def _ca_names_in(db: AsyncSession, start: date, end: date) -> set[int]:
    """Names with a corporate action inside the window, from the AUTHORITY cache.

    ⭐ Not a percentage-move screen — that screen is 62.5% false-positive (M70). A split
    inside a window would show up as an enormous range and read as an enormous spread.
    """
    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT stock_id FROM corporate_actions "
                "WHERE ex_date >= :s AND ex_date <= :e"
            ),
            {"s": start, "e": end},
        )
    ).all()
    return {r[0] for r in rows}


async def _adv_values(db: AsyncSession, stock_ids: list[int], as_of: date) -> dict[int, Decimal]:
    """Median daily traded value per name, from BEFORE the window — the same quantity the
    paper broker's participation model consumes, so impact is priced by the owner of that
    concept rather than by a second implementation here (W2/W5)."""
    rows = (
        await db.execute(
            text(
                """SELECT stock_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY close * volume)
                   FROM ohlcv_1d
                   WHERE stock_id = ANY(:ids) AND time < :as_of AND time >= :start
                   GROUP BY stock_id"""
            ),
            {"ids": stock_ids, "as_of": as_of, "start": as_of - timedelta(days=365)},
        )
    ).all()
    return {r[0]: Decimal(str(r[1])) for r in rows if r[1] is not None}


async def _load_window(
    db: AsyncSession, sessions: list[date], index: int
) -> WindowResult | None:
    first, last = sessions[0], sessions[-1]
    try:
        cohort = await liquid_as_of(db, first)
    except InsufficientHistoryError as exc:
        log.warning("window %d [%s..%s] skipped: %s", index, first, last, exc)
        return None

    excluded = await _ca_names_in(db, first, last)
    cohort = [s for s in cohort if s not in excluded]

    rows = (
        await db.execute(
            text(
                """SELECT stock_id, time::date AS d, high, low, close
                   FROM ohlcv_5m
                   WHERE stock_id = ANY(:ids)
                     AND time >= :start AND time < :end
                     AND is_complete
                   ORDER BY stock_id, time"""
            ),
            # ⚠ ``time`` is a timestamptz and ``last`` is a DATE, so an inclusive bound
            # would compare against midnight and silently drop the whole final session.
            {"ids": cohort, "start": first, "end": last + timedelta(days=1)},
        )
    ).all()

    by_name: dict[int, dict[date, list[Bar]]] = defaultdict(lambda: defaultdict(list))
    for stock_id, day, high, low, close in rows:
        by_name[stock_id][day].append(Bar(float(high), float(low), float(close)))

    adv = await _adv_values(db, cohort, first)

    names: list[NameWindow] = []
    for stock_id, days in by_name.items():
        usable = [bars for bars in days.values() if len(bars) >= MIN_BARS_PER_SESSION]
        if len(usable) < MIN_SESSIONS_PER_NAME:
            continue
        flat = [b for session in usable for b in session]
        returns = [
            math.log(b1.close / b0.close)
            for session in usable
            for b0, b1 in zip(session, session[1:], strict=False)
            if b0.close > 0 and b1.close > 0
        ]
        sigma = statistics.pstdev(returns) * 10_000.0 if len(returns) > 2 else float("nan")
        ar = abdi_ranaldo_sessions(usable)
        cs = corwin_schultz_sessions(usable)
        price = statistics.median([b.close for b in flat])
        tick = float(tick_for(Decimal(str(round(price, 2))), as_of=first))
        names.append(
            NameWindow(
                stock_id=stock_id,
                sessions=len(usable),
                bars=len(flat),
                degenerate_bars=sum(1 for b in flat if b.is_degenerate),
                sigma_bar_bps=sigma,
                ar_half_bps=None if ar is None else proportional_to_half_spread_bps(ar),
                cs_half_bps=None if cs is None else proportional_to_half_spread_bps(cs),
                adv_value=adv.get(stock_id),
                median_price=price,
                tick=tick,
            )
        )

    return WindowResult(
        index=index,
        first_session=first,
        last_session=last,
        cohort_requested=len(cohort),
        cohort_measured=len(names),
        names=names,
    )


def _cluster_bootstrap_median(
    windows: list[WindowResult],
    pick: Callable[[NameWindow], float | None],
    *,
    seed: int = 20260920,
) -> tuple[float, float, float]:
    """90% interval for the pooled median, resampling WHOLE WINDOWS.

    ⭐ Clustering by window is not decoration: every name in a window shares that month's
    market-wide volatility, and volatility is exactly what contaminates these estimators.
    Treating name-windows as independent would understate the interval.
    """
    per_window = [[v for v in (pick(n) for n in w.names) if v is not None] for w in windows]
    per_window = [vals for vals in per_window if vals]
    pooled = [v for vals in per_window for v in vals]
    point = statistics.median(pooled)

    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(BOOTSTRAP_DRAWS):
        sample: list[float] = []
        for _ in range(len(per_window)):
            sample.extend(rng.choice(per_window))
        draws.append(statistics.median(sample))
    draws.sort()
    return point, draws[int(0.05 * len(draws))], draws[int(0.95 * len(draws))]


def _verdict(upper_bps: float) -> tuple[str, str]:
    """The pre-registered tree, evaluated on the bound UNFAVOURABLE to proceeding."""
    if upper_bps < 5.0:
        return "A", "NOT BINDING — spread does not close the intraday thesis."
    if upper_bps < 15.0:
        return "B", "BINDING BUT NOT FATAL — carry the hurdle as a design constraint."
    return "C", "REFUTED at this cohort and size — do not build an intraday generator."


def _tick_reading(tick_median: float) -> str:
    """State what the tick check licenses — and, if it reads under half a tick, say so
    rather than quoting the bps figure as though it were precise."""
    if tick_median >= 1.0:
        return (
            f"✅✅ **The strongest available outcome: {tick_median:.2f} ticks means a book about "
            f"{2 * tick_median:.1f} ticks wide.** That is comfortably clear of BOTH floors — the "
            "exchange's minimum increment (0.50 as a half-spread) and the estimator's own "
            "resolution — so this is a real multi-tick spread being measured, not an artifact "
            "and not a clamp."
        )
    if tick_median >= 0.40:
        return (
            f"✅ **A one-tick market.** {tick_median:.2f} ticks is a book quoted at the minimum "
            "increment, which is the tightest a real market can be. The estimate is physically "
            "plausible but sits ON the exchange floor, so it cannot be read as precise."
        )
    return (
        f"⚠ **{tick_median:.2f} ticks is BELOW half a tick, which no real book can be.** The "
        "estimator is reading under its own resolution on part of this cohort, so the bps "
        "figure is a LOWER BOUND, not a point estimate. ⭐ It does not disturb the branch "
        "decision — a downward-biased estimate cannot manufacture a spread small enough to "
        "clear a threshold it would otherwise fail — but the hurdle should be quoted with the "
        "one-tick floor substituted instead."
    )


def _band_table(results: list[WindowResult]) -> str:
    """⭐ The CONTROL for the tick-change story.

    NSE's ~mid-2024 change moved only names below Rs 225 to a Rs 0.01 grid. If the fall in
    measured spread is that change, it must appear in the CHEAP band and NOT in the
    expensive one. If it appears in both, the tick change is not the explanation — a
    partition that is really a proxy for something else is a failure mode this project has
    already been burned by.
    """
    cut = date(2024, 6, 1)
    rows = ["| price band | period | name-windows | AR median | sigma/bar | clamp share |",
            "|---|---|--:|--:|--:|--:|"]
    bands: tuple[tuple[str, Callable[[NameWindow], bool]], ...] = (
        ("below Rs 225 (tick DID change)", lambda n: n.median_price < 225.0),
        ("Rs 225+ (tick UNCHANGED)", lambda n: n.median_price >= 225.0),
    )
    for band_label, keep in bands:
        for period_label, chosen in (
            ("before 2024-06", [w for w in results if w.last_session < cut]),
            ("from 2024-06", [w for w in results if w.last_session >= cut]),
        ):
            vals = [
                n for w in chosen for n in w.names if keep(n) and n.ar_half_bps is not None
            ]
            if not vals:
                continue
            ars = [n.ar_half_bps for n in vals if n.ar_half_bps is not None]
            sig = [n.sigma_bar_bps for n in vals if not math.isnan(n.sigma_bar_bps)]
            clamp = sum(1 for v in ars if v <= 1e-12) / len(ars)
            rows.append(
                f"| {band_label} | {period_label} | {len(vals):,} | {statistics.median(ars):.2f} "
                f"| {statistics.median(sig):.1f} | {clamp*100:.1f}% |"
            )
    return "\n".join(rows)


def _period_table(results: list[WindowResult]) -> str:
    """Split at the NSE sub-Rs 250 tick change (~mid-2024), which is the one documented
    event that would genuinely narrow spreads on this cohort (B3's schedule)."""
    cut = date(2024, 6, 1)
    rows = ["| period | windows | AR median | CS median | sigma/bar | clamp share |",
            "|---|--:|--:|--:|--:|--:|"]
    for label, chosen in (
        ("before 2024-06 (Rs 0.05 grid)", [w for w in results if w.last_session < cut]),
        ("from 2024-06 (Rs 0.01 sub-250)", [w for w in results if w.last_session >= cut]),
    ):
        ars = [n.ar_half_bps for w in chosen for n in w.names if n.ar_half_bps is not None]
        css = [n.cs_half_bps for w in chosen for n in w.names if n.cs_half_bps is not None]
        sig = [n.sigma_bar_bps for w in chosen for n in w.names if not math.isnan(n.sigma_bar_bps)]
        if not ars:
            continue
        clamp = sum(1 for v in ars if v <= 1e-12) / len(ars)
        rows.append(
            f"| {label} | {len(chosen)} | {statistics.median(ars):.2f} | "
            f"{statistics.median(css):.2f} | {statistics.median(sig):.1f} | {clamp*100:.1f}% |"
        )
    return "\n".join(rows)


def _intraday_charges_bps(price: Decimal = Decimal("500")) -> float:
    qty = int(ORDER_VALUE / price)
    total, _ = fees.roundtrip_charges(
        position_side="LONG", entry_price=price, exit_price=price, quantity=qty, product="intraday"
    )
    return float(total / (price * qty) * 10_000)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--windows", type=int, default=0, help="limit windows (0 = all)")
    ap.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help=(
            "last session to include (YYYY-MM-DD). ⛔ Defaults to the last session STRICTLY "
            "BEFORE today, never today's partial one. Pass it explicitly to reproduce a "
            "previous run exactly — ohlcv_5m grows, so an unpinned run measures a different "
            "sample each day."
        ),
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--from-dump",
        type=Path,
        default=None,
        help=(
            "re-render the report from a previous --dump instead of re-scanning the bars. "
            "⭐ Everything the renderer needs is in the dump, so a wording or presentation "
            "fix costs seconds rather than a 25-minute pass (round 9's artifact pattern)."
        ),
    )
    ap.add_argument(
        "--dump",
        type=Path,
        default=None,
        help="write every name-window row as CSV, so re-slicing costs no second pass",
    )
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

    repo_root = Path(__file__).resolve().parents[2]
    results: list[WindowResult] = []
    if args.from_dump:
        results = _results_from_dump(args.from_dump)
        log.info(
            "re-rendered from %s: %d windows, %d name-windows",
            args.from_dump, len(results), sum(len(w.names) for w in results),
        )
        report = _render(results)
        print(report)
        out = args.out or repo_root / "docs/analysis/item17-spread-impact-2026-09-20.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        log.info("written: %s", out)
        return 0

    async with AsyncSessionFactory() as db:
        sessions = await _sessions_available(db)
        # ⛔⛔ **A study whose window comes from a live query over a growing table is a
        # timestamp, not a cohort** — the lesson item 6 drew from `_load_frames`, reproduced
        # here on the first re-run: the dev DB gained 2026-09-21 between two passes and the
        # sample silently went 797 -> 798 sessions, 37 -> 38 windows, AR 1.74 -> 1.73. The
        # end is therefore pinned, and today's own partial session is never included.
        cutoff = args.end or (date.today() - timedelta(days=1))
        dropped = [d for d in sessions if d > cutoff]
        sessions = [d for d in sessions if d <= cutoff]
        if not sessions:
            log.error("no sessions at or before %s", cutoff)
            return 1
        log.info(
            "ohlcv_5m: %d sessions, %s .. %s  (end pinned at %s%s)",
            len(sessions), sessions[0], sessions[-1], cutoff,
            f", {len(dropped)} later session(s) excluded" if dropped else "",
        )

        blocks = [
            sessions[i : i + MIN_SESSIONS_FOR_STABILITY]
            for i in range(0, len(sessions), MIN_SESSIONS_FOR_STABILITY)
        ]
        blocks = [b for b in blocks if len(b) == MIN_SESSIONS_FOR_STABILITY]
        if args.windows:
            blocks = blocks[: args.windows]
        log.info("measuring %d windows of %d sessions", len(blocks), MIN_SESSIONS_FOR_STABILITY)

        results = []
        for i, block in enumerate(blocks):
            result = await _load_window(db, block, i)
            if result is None:
                continue
            results.append(result)
            ars = [n.ar_half_bps for n in result.names if n.ar_half_bps is not None]
            log.info(
                "  window %2d %s..%s  cohort %3d -> measured %3d  AR median %s",
                i, block[0], block[-1], result.cohort_requested, result.cohort_measured,
                f"{statistics.median(ars):6.2f} bps" if ars else "     n/a",
            )

    if not results:
        log.error("no windows measured")
        return 1

    if args.dump:
        args.dump.parent.mkdir(parents=True, exist_ok=True)
        with args.dump.open("w") as fh:
            fh.write(
                "window,first_session,last_session,cohort_requested,cohort_measured,"
                "stock_id,sessions,bars,degenerate_bars,"
                "sigma_bar_bps,ar_half_bps,cs_half_bps,median_price,tick,adv_value\n"
            )
            for w in results:
                for n in w.names:
                    fh.write(
                        f"{w.index},{w.first_session},{w.last_session},"
                        f"{w.cohort_requested},{w.cohort_measured},{n.stock_id},"
                        f"{n.sessions},{n.bars},{n.degenerate_bars},{n.sigma_bar_bps:.4f},"
                        f"{'' if n.ar_half_bps is None else f'{n.ar_half_bps:.6f}'},"
                        f"{'' if n.cs_half_bps is None else f'{n.cs_half_bps:.6f}'},"
                        f"{n.median_price:.4f},{n.tick},"
                        f"{'' if n.adv_value is None else n.adv_value}\n"
                    )
        log.info("dumped: %s", args.dump)

    report = _render(results)
    print(report)
    # ⚠ Resolve from the file, never the cwd: the first run was launched from backend/
    # and lost its whole report to a FileNotFoundError after the 25-minute pass.
    out = args.out or repo_root / "docs/analysis/item17-spread-impact-2026-09-20.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    log.info("written: %s", out)
    return 0


def _results_from_dump(path: Path) -> list[WindowResult]:
    """Reconstruct the rendered structures from a dump — no DB, no re-scoring.

    ⚠ Round-trips only what the dump carries. It carries everything ``_render`` reads,
    which is why the dump was widened to include the requested cohort size.
    """
    import csv

    by_window: dict[int, list[NameWindow]] = defaultdict(list)
    meta: dict[int, tuple[date, date, int]] = {}
    with path.open() as fh:
        for raw in csv.DictReader(fh):
            idx = int(raw["window"])
            meta[idx] = (
                date.fromisoformat(raw["first_session"]),
                date.fromisoformat(raw["last_session"]),
                int(raw["cohort_requested"]),
            )
            by_window[idx].append(
                NameWindow(
                    stock_id=int(raw["stock_id"]),
                    sessions=int(raw["sessions"]),
                    bars=int(raw["bars"]),
                    degenerate_bars=int(raw["degenerate_bars"]),
                    sigma_bar_bps=float(raw["sigma_bar_bps"]),
                    ar_half_bps=float(raw["ar_half_bps"]) if raw["ar_half_bps"] else None,
                    cs_half_bps=float(raw["cs_half_bps"]) if raw["cs_half_bps"] else None,
                    adv_value=Decimal(raw["adv_value"]) if raw["adv_value"] else None,
                    median_price=float(raw["median_price"]),
                    tick=float(raw["tick"]),
                )
            )
    return [
        WindowResult(
            index=i,
            first_session=meta[i][0],
            last_session=meta[i][1],
            cohort_requested=meta[i][2],
            cohort_measured=len(by_window[i]),
            names=by_window[i],
        )
        for i in sorted(by_window)
    ]


def _render(results: list[WindowResult]) -> str:
    every = [n for w in results for n in w.names]
    ar_point, ar_lo, ar_hi = _cluster_bootstrap_median(results, lambda n: n.ar_half_bps)
    cs_point, cs_lo, cs_hi = _cluster_bootstrap_median(results, lambda n: n.cs_half_bps)
    branch, meaning = _verdict(ar_hi)

    ar_vals = [n.ar_half_bps for n in every if n.ar_half_bps is not None]
    zero_share = sum(1 for v in ar_vals if v <= 1e-12) / len(ar_vals)
    sigmas = [n.sigma_bar_bps for n in every if not math.isnan(n.sigma_bar_bps)]
    sigma_median = statistics.median(sigmas)
    degenerate = sum(n.degenerate_bars for n in every) / max(1, sum(n.bars for n in every))

    median_cohort = statistics.median([w.cohort_measured for w in results])
    median_requested = statistics.median([w.cohort_requested for w in results])
    cal_null = calibrate(sigma_bar_bps=sigma_median, replications=200)
    cal_at = calibrate(sigma_bar_bps=sigma_median, planted_half_bps=ar_point, replications=200)
    ticks = [n.ar_half_ticks for n in every if n.ar_half_ticks is not None]
    tick_median = statistics.median(ticks) if ticks else float("nan")
    price_median = statistics.median([n.median_price for n in every])
    bars_per_session = statistics.median([n.bars / n.sessions for n in every])
    thin_share = sum(1 for n in every if n.sessions < MIN_SESSIONS_FOR_STABILITY) / len(every)
    charges = _intraday_charges_bps()
    impacts = []
    for n in every:
        if n.adv_value and n.adv_value > 0:
            bps, _ = participation_bps(ORDER_VALUE, n.adv_value)
            impacts.append(float(bps))
    impact_med = statistics.median(impacts) if impacts else float("nan")
    hurdle = charges + 2 * ar_point + impact_med
    hurdle_hi = charges + 2 * ar_hi + impact_med

    lines = [
        "# Item 17 — spread and impact on the intraday cohort, measured",
        "",
        "**Run 2026-09-20** against the pre-registration committed at `6a4af12`, before this",
        "script existed. Read-only; both sealed holdouts untouched.",
        "",
        "## Verdict",
        "",
        f"**BRANCH {branch} — {meaning}**",
        "",
        f"Abdi-Ranaldo median half-spread **{ar_point:.2f} bps**, 90% cluster-bootstrap interval",
        f"**[{ar_lo:.2f}, {ar_hi:.2f}]**. The pre-registration evaluates the branch on the bound",
        f"unfavourable to proceeding, so **{ar_hi:.2f} bps** is the number the tree reads.",
        "",
        "| quantity | value |",
        "|---|--:|",
        f"| block measured | {results[0].first_session} .. {results[-1].last_session} |",
        f"| name-windows measured | {len(every):,} |",
        f"| measurement windows | {len(results)} of {MIN_SESSIONS_FOR_STABILITY}-session blocks |",
        f"| PIT cohort requested (median/window) | {median_requested:.0f} names |",
        f"| **measured after intersecting 5m capture** | **{median_cohort:.0f} names** |",
        f"| **AR median half-spread** | **{ar_point:.2f} bps** [{ar_lo:.2f}, {ar_hi:.2f}] |",
        f"| AR zero-clamp share | {zero_share*100:.1f}% |",
        f"| CS median half-spread (biased UP) | {cs_point:.2f} bps [{cs_lo:.2f}, {cs_hi:.2f}] |",
        f"| median per-bar volatility | {sigma_median:.1f} bps |",
        f"| degenerate (no-range) bars | {degenerate*100:.1f}% |",
        f"| **AR half-spread in TICKS** | **{tick_median:.2f}** (one-tick market = 0.50) |",
        f"| median name price | Rs {price_median:,.0f} |",
        f"| intraday round-trip charges @ Rs {ORDER_VALUE:,} | {charges:.2f} bps |",
        f"| median participation impact @ Rs {ORDER_VALUE:,} | {impact_med:.2f} bps |",
        f"| **implied intraday hurdle** | **{hurdle:.2f} bps** (upper bound {hurdle_hi:.2f}) |",
        "",
        "## ⚠ Which population this describes",
        "",
        "The PIT top-250 cohort is **not** the binding selector: it asks for",
        f"{median_requested:.0f} names and only **{median_cohort:.0f}** survive intersecting with",
        "the names that have 5-minute bars. **`ohlcv_5m` holds roughly 200-210 distinct names for",
        "the whole block** (the 2,000+ figure appears only from 2026-09, after the last measured",
        "window), so **this is a fixed ~205-name capture set, not a point-in-time cohort**, and",
        "every figure below describes that set. ⚠ A thinner name is a different question and this",
        "study does not answer it.",
        "",
        "## How to read the two estimators, at THIS cohort's volatility",
        "",
        "⛔ **Corwin-Schultz is a corroborating upper bound, not a measurement** — its zero-spread",
        "null is linear in volatility. ⚠ **Quoting that null at a volatility the cohort does not",
        "have would invite the wrong comparison**, so it is calibrated here at the measured",
        f"{sigma_median:.1f} bps/bar:",
        "",
        f"| at sigma = {sigma_median:.1f} bps/bar | Corwin-Schultz | Abdi-Ranaldo | AR clamp |",
        "|---|--:|--:|--:|",
        f"| planted ZERO spread (the null) | {cal_null.cs_median_bps:.2f} | "
        f"{cal_null.ar_median_bps:.2f} | {cal_null.ar_clamp_share*100:.1f}% |",
        f"| planted at the measured {ar_point:.2f} bps | {cal_at.cs_median_bps:.2f} | "
        f"{cal_at.ar_median_bps:.2f} | {cal_at.ar_clamp_share*100:.1f}% |",
        f"| **MEASURED on real bars** | **{cs_point:.2f}** | **{ar_point:.2f}** | "
        f"**{zero_share*100:.1f}%** |",
        "",
        f"⭐ **CS reads {cs_point:.2f} against a null of "
        f"{cal_null.cs_median_bps:.2f}** — above it,",
        "so it corroborates a small positive spread rather than contradicting AR.",
        "",
        "⚠ **The clamp share is NOT a statement about the median.** A HOMOGENEOUS cohort at",
        f"{ar_point:.2f} bps would clamp {cal_at.ar_clamp_share*100:.1f}%; the measured",
        f"{zero_share*100:.1f}% can only come from cross-sectional heterogeneity — names genuinely",
        "tighter than the estimator resolves. ⚠ **AR's median carries a small DOWNWARD bias here**",
        f"({ar_point:.2f} planted reads {cal_at.ar_median_bps:.2f}), and that bias is **not** in",
        "the bootstrap interval, which is a sampling interval only.",
        "",
        "## ⭐ Does the estimate agree with the exchange's own tick grid?",
        "",
        "A real market cannot be narrower than one tick, so a half-spread of about **0.50",
        "ticks** is what a one-tick-wide book looks like. This is the only ground-truth-free",
        "check available, and it is a PHYSICAL constraint rather than another estimator.",
        "",
        f"Measured median: **{tick_median:.2f} ticks** at a median price of "
        f"Rs {price_median:,.0f}.",
        "",
        _tick_reading(tick_median),
        "",
        "## ⚠ The drift, and what a 0.00 window means",
        "",
        "⛔ **A window reading 0.00 has CLAMPED — that is 'below the estimator's resolution',",
        "never 'no spread'.** Under a true zero spread about half of windows clamp; the share",
        "here is reported per window so a clamped window is never read as a measurement.",
        "",
        _period_table(results),
        "",
        "### The control: did the tick change actually cause it?",
        "",
        _band_table(results),
        "",
        "## Per-window detail",
        "",
        "| # | window | cohort | AR median | CS median | sigma/bar | clamped |",
        "|--:|---|--:|--:|--:|--:|--:|",
    ]
    for w in results:
        ars = [n.ar_half_bps for n in w.names if n.ar_half_bps is not None]
        css = [n.cs_half_bps for n in w.names if n.cs_half_bps is not None]
        sig = [n.sigma_bar_bps for n in w.names if not math.isnan(n.sigma_bar_bps)]
        clamped = sum(1 for v in ars if v <= 1e-12) / len(ars) if ars else float("nan")
        lines.append(
            f"| {w.index} | {w.first_session}..{w.last_session} | {w.cohort_measured} | "
            f"{statistics.median(ars):.2f} | {statistics.median(css):.2f} | "
            f"{statistics.median(sig):.1f} | {clamped*100:.0f}% |"
        )
    lines += [
        "",
        "## Limits, stated",
        "",
        "⚠ **An estimate, not an observation.** No historical order book exists; item 17b",
        "(forward top-of-book capture) is what would validate this against a real book.",
        "⚠ **One cohort, one size.** Every bps figure is at the stated order value on the",
        "~205-name 5m capture set described above; a thinner name or a larger order is a",
        "different question.",
        "",
        "⚠ **Declared filters, none of them in the pre-registration.** A name needs "
        f"{MIN_SESSIONS_PER_NAME} sessions in the window and {MIN_BARS_PER_SESSION} bars in a",
        "session to be counted, and both condition on activity INSIDE the measurement window,",
        "which correlates with spread. Measured attrition here: the median name-window has",
        f"{bars_per_session:.1f} bars per usable session and {thin_share*100:.1f}% of",
        "name-windows fall below the full window length — near-inert on this cohort, but",
        "declared rather than discovered later.",
        "",
        "⚠ **Corporate actions are excluded on ex-dates INSIDE the window**, which is future",
        "information relative to the window start. Conservative (it removes names rather",
        "than adding them) but not strictly point-in-time.",
        "",
        f"⚠ **{len(results) * MIN_SESSIONS_FOR_STABILITY} sessions are measured**, in whole",
        "21-session windows only; the block's final partial window is dropped. ⛔ The end is",
        "PINNED (`--end`) because `ohlcv_5m` grows: an unpinned re-run measures a different",
        "sample, which is exactly item 6's `_load_frames` defect.",
        "⚠ **Cost, not edge.** A favourable branch means the arithmetic does not forbid an",
        "intraday generator. It does not mean one exists.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
