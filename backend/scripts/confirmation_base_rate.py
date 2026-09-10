"""Base rate: does trading through yesterday's high carry forward edge, on its own?

The entry-confirmation study measures the rule on OUR signals (~3k trades). This measures the
MECHANISM on every (stock, day) in the same universe (~137k bars), which answers a different and
prior question: if "price broke yesterday's high" carries no unconditional forward edge, then a
confirmation rule can only work through SELECTION of our signals, never through momentum. That
distinction decides whether the rule generalises or is fitted to our signal set.

Three pre-registered hypotheses, one per author. No sweeping.
  H-A  (Elder/Brooks/Livermore)  entry at max(open, prior high + tick) on days that trade
        through the prior high beats entry at the open on all days.
  H-A2 (Weinstein specifically)  the same, but REFUSING a fill worse than the trigger plus
        `_CEILING_PCT` - his "Buy 1,000 XYZ at 12 1/8 stop - 12 3/8 limit", i.e. confirm but do
        not chase a gap. H-A alone does NOT test Weinstein: it buys any gap, however large,
        which is the exact failure his stop-limit exists to prevent.
  H-B (Weinstein, 30-week MA / Stage 2)   H-A is stronger when the prior close is above a
        rising 150-day MA, and absent or negative below it.
  H-C (Elder, Market Thermometer)         entering on a QUIET bar (today's extension beyond
        yesterday's range below its own 22-day EMA) beats entering on a HOT one.

TWO MEASUREMENT BASES, because one of them is contaminated. A return measured from the TRIGGER
price to close[t+k] spans the remainder of day t, so a bar that has already run far past the
trigger books that run as "forward" return. That mechanically favours the HOT cohort in H-C and
any cohort correlated with same-day drift. So every conditional split is reported on BOTH bases:
  from trigger   the implementable P&L of the rule (contaminated for cross-cohort comparison)
  from close[t]  strictly forward of the entry day - the basis to read for H-B and H-C
The headline H-A comparison is unaffected in the direction that matters: the contamination
FAVOURS the confirmed-at-trigger cohort, so a negative result there is conservative.

INFERENCE (corrected 2026-09-10 after a quant-verifier HIGH). Forward-return windows overlap
across days AND stocks. Averaging the cross-section within each trading day removes the SAME-DAY
dependence but leaves the ACROSS-DAY overlap untouched: day t and day t+1 share k-1 sessions of
the same future. A naive t on that daily series is inflated by roughly sqrt(k) - measured under
H0 on this panel shape its sd is 0.98 at k=1 but 3.32 at k=10 and 4.45 at k=20. So the reported
t is Newey-West with Bartlett weights at lag = k-1 (`app.services.block_bootstrap.newey_west_t`),
and the naive t is printed beside it so the size of the correction stays visible.

CORPUS (corrected 2026-09-10). `ohlcv_1d` is CA-UNADJUSTED and the 2023-07-03 window is NOT
"CA-clean" as this file previously claimed: 49 unadjusted corporate actions sit inside this exact
250-stock universe, 35 of them >=40% halvings (SHRIRAMFIN -81.1%, COFORGE -79.7%, ANGELONE
-90.1%, ...). A split gap is not noise here - it is a fake -80% return that no filter downstream
can distinguish from a crash. Observations whose forward window contains a |close-to-close| jump
greater than `_CA_JUMP` are therefore DROPPED, and the count is printed in the report header.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.block_bootstrap import newey_west_t  # noqa: E402
from sqlalchemy import text  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_CLEAN_SINCE = datetime(2023, 7, 3, tzinfo=UTC)
_TICK = 0.05
_HORIZONS = (1, 3, 5, 10)
# A close-to-close move this large in a liquid name is a split/bonus, not a trade.
_CA_JUMP = 0.25
# Weinstein's limit sits 1/4 point above a ~12 breakout ~= 2%; 1/2 point (~4%) for a thin name.
_CEILING_PCT = 0.02


async def _load(max_stocks: int, min_rows: int) -> dict[str, pd.DataFrame]:
    async with AsyncSessionFactory() as db:
        pick = await db.execute(
            text(
                "SELECT s.symbol, percentile_cont(0.5) WITHIN GROUP "
                "(ORDER BY o.close*o.volume) mdv "
                "FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                "WHERE s.is_active AND o.time >= :since "
                "GROUP BY s.symbol HAVING COUNT(*) >= :min_rows ORDER BY mdv DESC"
            ),
            {"since": _CLEAN_SINCE, "min_rows": min_rows},
        )
        syms = [r.symbol for r in pick.fetchall() if r.mdv is not None and float(r.mdv) >= 5e7][
            :max_stocks
        ]
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close "
                    "FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                    "WHERE s.symbol = ANY(:syms) AND o.time >= :since "
                    "ORDER BY s.symbol, o.time"
                ),
                {"syms": syms, "since": _CLEAN_SINCE},
            )
        ).fetchall()
    by: dict[str, list[Any]] = defaultdict(list)
    for r in rows:
        by[r.symbol].append(r)
    return {
        s: pd.DataFrame(
            {
                "time": [r.time for r in rs],
                "open": [float(r.open) for r in rs],
                "high": [float(r.high) for r in rs],
                "low": [float(r.low) for r in rs],
                "close": [float(r.close) for r in rs],
            }
        ).set_index("time")
        for s, rs in by.items()
    }


def _daily_t(
    per_day: dict[pd.Timestamp, list[float]], horizon: int
) -> tuple[float, float, float, int]:
    """Mean, Newey-West t, naive t, and n of the DAILY CROSS-SECTIONAL mean series.

    The NW t (lag = horizon-1) is the one to read; the naive t is returned only so the report
    can show how large the overlap correction is.
    """
    series = [statistics.mean(v) for v in per_day.values() if v]
    n = len(series)
    if n < 3:
        return 0.0, 0.0, 0.0, n
    m = statistics.mean(series)
    sd = statistics.stdev(series)
    naive = m / (sd / n**0.5) if sd > 0 else 0.0
    nw = newey_west_t(series, lag=horizon - 1)
    return m, (nw if nw is not None else 0.0), naive, n


def main() -> None:  # noqa: C901 - one linear pass: load, accumulate, render
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    out_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(_OUT_DIR / f"confirmation-base-rate-{datetime.now(tz=UTC).date()}.md")
    )
    frames = asyncio.run(_load(max_stocks=250, min_rows=200))
    print(f"loaded {len(frames)} stocks", file=sys.stderr)

    # accumulators: label -> horizon -> {date: [pct returns]}
    acc: dict[str, dict[int, dict[pd.Timestamp, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    n_bars = 0
    n_conf = 0
    n_ca_dropped = 0

    for _sym, df in frames.items():
        o = df["open"].to_numpy()
        h = df["high"].to_numpy()
        c = df["close"].to_numpy()
        low = df["low"].to_numpy()
        idx = df.index
        m = len(df)
        if m < 160 + max(_HORIZONS):
            continue

        # A CA bar is one whose close-to-close move is impossibly large for a liquid name.
        c2c = np.concatenate([[0.0], np.abs(np.diff(c) / c[:-1])])
        is_ca = c2c > _CA_JUMP

        ma150 = pd.Series(c).rolling(150).mean().to_numpy()
        ma150_up = np.concatenate([[np.nan], np.diff(ma150)]) > 0
        # Elder Market Thermometer: max(H-H[-1], L[-1]-L), and its 22-day EMA
        ext_up = h[1:] - h[:-1]
        ext_dn = low[:-1] - low[1:]
        temp = np.concatenate([[np.nan], np.maximum(ext_up, ext_dn)])
        temp_ema = pd.Series(temp).ewm(span=22, adjust=False).mean().to_numpy()

        for t in range(151, m - max(_HORIZONS)):
            n_bars += 1
            trigger = h[t - 1] + _TICK
            confirmed = h[t] >= trigger
            entry_conf = max(o[t], trigger)
            date = idx[t]

            for k in _HORIZONS:
                # Drop the observation at THIS horizon if an unadjusted corporate action
                # falls inside its forward window: the "return" would be a split, not a move.
                if bool(is_ca[t : t + k + 1].any()):
                    n_ca_dropped += 1
                    continue
                base_ret = (c[t + k] - o[t]) / o[t] * 100.0
                acc["all: enter at open"][k][date].append(base_ret)
                if confirmed:
                    conf_ret = (c[t + k] - entry_conf) / entry_conf * 100.0
                    acc["confirmed: enter at trigger"][k][date].append(conf_ret)
                    acc["confirmed: enter at open (same days)"][k][date].append(base_ret)
                    # H-A2: Weinstein's stop-LIMIT - the fill is refused if the open gapped
                    # more than the ceiling past the trigger. A refused fill is not a trade,
                    # so it contributes nothing (it is not a zero).
                    if entry_conf <= trigger * (1 + _CEILING_PCT):
                        acc["confirmed + under a 2% ceiling (Weinstein)"][k][date].append(conf_ret)
                    # H-B: Weinstein stage filter
                    above = c[t - 1] > ma150[t - 1] if not np.isnan(ma150[t - 1]) else False
                    rising = bool(ma150_up[t - 1])
                    fwd_ret = (c[t + k] - c[t]) / c[t] * 100.0  # strictly forward of day t
                    tag = "above rising 150DMA" if (above and rising) else "NOT above rising 150DMA"
                    acc[f"confirmed + {tag} [from trigger]"][k][date].append(conf_ret)
                    acc[f"confirmed + {tag} [from close]"][k][date].append(fwd_ret)
                    # H-C: Elder thermometer state of the ENTRY bar
                    if not np.isnan(temp[t]) and not np.isnan(temp_ema[t]):
                        state = "QUIET bar" if temp[t] < temp_ema[t] else "HOT bar"
                        acc[f"confirmed + {state} [from trigger]"][k][date].append(conf_ret)
                        acc[f"confirmed + {state} [from close]"][k][date].append(fwd_ret)
                else:
                    acc["not confirmed: enter at open"][k][date].append(base_ret)
            if confirmed:
                n_conf += 1

    lines: list[str] = []
    a = lines.append
    a("# Confirmation base rate - does breaking yesterday's high pay, on its own?\n")
    a(
        f"_Generated {datetime.now(tz=UTC).date()} - 250 liquid stocks - window from "
        f"{_CLEAN_SINCE.date()} - {n_bars:,} stock-days, {n_conf:,} ({n_conf / n_bars * 100:.1f}%) "
        f"traded through the prior high. **{n_ca_dropped:,} stock-day/horizon observations "
        f"dropped** because an unadjusted corporate action (|close-to-close| > "
        f"{_CA_JUMP * 100:.0f}%) fell inside the forward window._\n"
    )
    a(
        "\nForward return in %, from the stated entry price to the close k sessions later. "
        "**`t` is Newey-West at lag k-1 on the daily cross-sectional mean series**; `naive t` "
        "is the uncorrected one, shown only so the size of the overlap correction is visible. "
        "Averaging the cross-section removes same-day dependence but NOT the overlap between "
        "day t and day t+1, which share k-1 sessions of the same future - under H0 that "
        "inflates the naive t by ~sqrt(k) (sd 3.32 at k=10, 4.45 at k=20).\n"
    )
    order = [
        "all: enter at open",
        "confirmed: enter at open (same days)",
        "confirmed: enter at trigger",
        "confirmed + under a 2% ceiling (Weinstein)",
        "not confirmed: enter at open",
        "confirmed + above rising 150DMA [from trigger]",
        "confirmed + NOT above rising 150DMA [from trigger]",
        "confirmed + above rising 150DMA [from close]",
        "confirmed + NOT above rising 150DMA [from close]",
        "confirmed + QUIET bar [from trigger]",
        "confirmed + HOT bar [from trigger]",
        "confirmed + QUIET bar [from close]",
        "confirmed + HOT bar [from close]",
    ]
    for k in _HORIZONS:
        a(f"\n## Horizon: close in +{k} session(s)\n")
        a("\n| cohort | stock-days | mean fwd % | t (Newey-West) | naive t |")
        a("|---|---|---|---|---|")
        for label in order:
            if label not in acc:
                continue
            per_day = acc[label][k]
            total = sum(len(v) for v in per_day.values())
            mean_pct, tstat, naive, ndays = _daily_t(per_day, k)
            a(
                f"| {label} | {total:,} | {mean_pct:+.3f}% | {tstat:+.2f} ({ndays}d) | "
                f"{naive:+.2f} |"
            )

    a("\n## The hypotheses, actually tested\n")
    a(
        "Every table above reports the t of a LEVEL. A hypothesis is a DIFFERENCE, so each row "
        "here builds the daily series `mean(A) - mean(B)` over the days both cohorts occupy and "
        "reports the Newey-West t of that one series. This is the only place H-A/H-A2/H-B/H-C "
        "are decided; the level t's above cannot do it.\n"
    )
    a("\n| hypothesis | A - B | horizon | days | mean diff | t (Newey-West) |")
    a("|---|---|---|---|---|---|")
    hyps = [
        (
            "H-A",
            "confirmed: enter at trigger",
            "all: enter at open",
        ),
        (
            "H-A2",
            "confirmed + under a 2% ceiling (Weinstein)",
            "all: enter at open",
        ),
        (
            "H-B",
            "confirmed + above rising 150DMA [from close]",
            "confirmed + NOT above rising 150DMA [from close]",
        ),
        (
            "H-C",
            "confirmed + QUIET bar [from close]",
            "confirmed + HOT bar [from close]",
        ),
    ]
    for name, a_lbl, b_lbl in hyps:
        for k in _HORIZONS:
            pa, pb = acc.get(a_lbl, {}).get(k, {}), acc.get(b_lbl, {}).get(k, {})
            shared = sorted(set(pa) & set(pb))
            diffs = [statistics.mean(pa[d]) - statistics.mean(pb[d]) for d in shared]
            if len(diffs) < 3:
                a(f"| {name} | {a_lbl} - {b_lbl} | +{k}d | {len(diffs)} | - | - |")
                continue
            nw = newey_west_t(diffs, lag=k - 1)
            a(
                f"| {name} | `{a_lbl}` - `{b_lbl}` | +{k}d | {len(diffs)} | "
                f"{statistics.mean(diffs):+.3f}% | {nw if nw is None else f'{nw:+.2f}'} |"
            )

    a("\n## Reading it\n")
    a(
        "- **`confirmed: enter at open (same days)` is NOT a strategy.** It uses information "
        "(that the day WILL trade through the prior high) that does not exist at the open. It is "
        "here only to decompose the rule: against `confirmed: enter at trigger` it isolates the "
        "**price paid** for confirmation with the day set held fixed, and against `not "
        "confirmed` it isolates the **selection** effect.\n"
        "- The only two implementable rows are `all: enter at open` and `confirmed: enter at "
        "trigger`. Those are the two that decide H-A.\n"
        "- For H-B and H-C read the `[from close]` rows: `[from trigger]` spans the rest of the "
        "entry day and so rewards a bar that has already run.\n"
    )
    Path(out_path).write_text("\n".join(lines))
    print("\n".join(lines))


# Usage:
#     uv run python scripts/confirmation_base_rate.py [out.md]


if __name__ == "__main__":
    main()
