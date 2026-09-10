"""Base rate: does trading through yesterday's high carry forward edge, on its own?

The entry-confirmation study measures the rule on OUR signals (~3k trades). This measures the
MECHANISM on every (stock, day) in the same universe (~137k bars), which answers a different and
prior question: if "price broke yesterday's high" carries no unconditional forward edge, then a
confirmation rule can only work through SELECTION of our signals, never through momentum. That
distinction decides whether the rule generalises or is fitted to our signal set.

Three pre-registered hypotheses, one per author. No sweeping.
  H-A (Elder/Weinstein/Brooks/Livermore)  entry at max(open, prior high + tick) on days that
        trade through the prior high beats entry at the open on all days.
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

INFERENCE. Forward-return windows overlap heavily across days AND stocks, so a naive per-trade
t-statistic is badly inflated. Everything below is therefore tested on the DAILY CROSS-SECTIONAL
MEAN: average the per-stock value within each trading day, then t-test that one series across
days (n = trading days). That neutralises the dominant dependence (same-day market moves) and is
the only t we report.
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
from sqlalchemy import text  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_CLEAN_SINCE = datetime(2023, 7, 3, tzinfo=UTC)
_TICK = 0.05
_HORIZONS = (1, 3, 5, 10)


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


def _daily_t(per_day: dict[pd.Timestamp, list[float]]) -> tuple[float, float, int]:
    """Mean and t of the DAILY CROSS-SECTIONAL mean series (the only honest t here)."""
    series = [statistics.mean(v) for v in per_day.values() if v]
    n = len(series)
    if n < 3:
        return 0.0, 0.0, n
    m = statistics.mean(series)
    sd = statistics.stdev(series)
    return m, (m / (sd / n**0.5) if sd > 0 else 0.0), n


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

    for _sym, df in frames.items():
        o = df["open"].to_numpy()
        h = df["high"].to_numpy()
        c = df["close"].to_numpy()
        low = df["low"].to_numpy()
        idx = df.index
        m = len(df)
        if m < 160 + max(_HORIZONS):
            continue

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
                base_ret = (c[t + k] - o[t]) / o[t] * 100.0
                acc["all: enter at open"][k][date].append(base_ret)
                if confirmed:
                    conf_ret = (c[t + k] - entry_conf) / entry_conf * 100.0
                    acc["confirmed: enter at trigger"][k][date].append(conf_ret)
                    acc["confirmed: enter at open (same days)"][k][date].append(base_ret)
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
        f"_Generated {datetime.now(tz=UTC).date()} - 250 liquid stocks - CA-clean window from "
        f"{_CLEAN_SINCE.date()} - {n_bars:,} stock-days, {n_conf:,} ({n_conf / n_bars * 100:.1f}%) "
        f"traded through the prior high._\n"
    )
    a(
        "\nForward return in %, from the stated entry price to the close k sessions later. "
        "**t is computed on the daily cross-sectional mean series** (n = trading days), never "
        "per trade - overlapping windows across days and stocks would inflate a per-trade t by "
        "roughly an order of magnitude.\n"
    )
    order = [
        "all: enter at open",
        "confirmed: enter at open (same days)",
        "confirmed: enter at trigger",
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
        a("\n| cohort | stock-days | mean fwd % | t (daily x-sec) |")
        a("|---|---|---|---|")
        for label in order:
            if label not in acc:
                continue
            per_day = acc[label][k]
            total = sum(len(v) for v in per_day.values())
            mean_pct, tstat, ndays = _daily_t(per_day)
            a(f"| {label} | {total:,} | {mean_pct:+.3f}% | {tstat:+.2f} ({ndays}d) |")

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
