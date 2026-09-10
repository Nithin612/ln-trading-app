"""Overhead supply: does trapped volume between price and the target stop the target being hit?

Weinstein's buy checklist (`Secrets for Profiting...`, ch4) has four conditions, and the third is
the one we have never computed:

    "the chart from that favorable group must be breaking out into Stage 2 **with a minimum of
     resistance overhead**. Finally, volume most definitely must confirm the breakout."

Damir reaches the same place from market profile: a value area's boundary is where the bulk of
volume traded, and it "acts as a support/resistance level" - price arriving there meets the
supply that accumulated there.

WHY THIS ONE MATTERS HERE. Our frozen swing geometry is a structural stop paired with a flat +6%
target (`app/analysis/risk.py compute_levels`). Nothing in the pipeline asks whether that +6% is
*reachable* - whether a wall of prior volume sits between the entry and it. The allowed cohort
hits its target only 16% of the time. If overhead supply predicts non-reachability, it is an
eligibility test (a veto, never a score term) that attacks that number directly.

MEASURE. At day t, over the trailing 250 sessions, `overhead` = the share of traded volume that
changed hands inside the band (close[t], close[t] x 1.06] - i.e. between here and where the swing
target would sit. Volume is attributed to each bar's CLOSE (a bar's volume cannot be split across
its range without intraday data we no longer hold; the coarseness is symmetric across quintiles).

TWO PRE-REGISTERED OUTCOMES, both long-side (the target geometry under test):
  O-1  P(high reaches +6% within k sessions) - literally the tp_hit question.
  O-2  forward excess return, market-demeaned by the daily cross-section (the corpus window is a
       strong bull market; a raw long-only number would look free).

Inference on the daily mean across trading days (n = days), never per trade - forward windows
overlap heavily across days and stocks.

THE MANDATORY PROXY CHECK (hard constraint #8: "check the partition isn't a proxy for something
else" - market-regime turned out to be a proxy for SIDE). `overhead` has two obvious alternative
readings, and both are measured here, not argued away:

  VOLATILITY  a 6%-wide band captures a large share of a low-volatility stock's volume and a
              small share of a high-volatility one's, so low overhead may simply mean "volatile",
              which trivially reaches +/-6% more often.
  MOMENTUM    low overhead means the trailing volume traded BELOW today's price, i.e. the stock
              has RISEN. Overhead may therefore be an inverse price-momentum proxy - and price
              momentum is one of the best-documented equity anomalies, so "it is momentum" is the
              null hypothesis to beat, not a discovery.

So the gradient is re-reported WITHIN volatility terciles and WITHIN 12-month-momentum terciles.
If it survives inside a momentum tercile it is incremental to momentum; if it collapses, it IS
momentum wearing a different name.
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
_LOOKBACK = 250
_TARGET_PCT = 0.06  # the frozen swing target
_HORIZONS = (5, 10, 20)
_QUINTILES = 5
# A close-to-close move this large in a liquid name is a split/bonus, not a trade.
_CA_JUMP = 0.25
# The downside counterpart to the +6% target: the frozen swing SL cap (SIGNAL_ENGINE.md §6).
_STOP_PCT = 0.08


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
        syms = [r.symbol for r in pick.fetchall() if r.mdv and float(r.mdv) >= 5e7][:max_stocks]
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume "
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
                "volume": [float(r.volume) for r in rs],
            }
        ).set_index("time")
        for s, rs in by.items()
    }


def _daily_t(per_day: dict[Any, list[float]], horizon: int) -> tuple[float, float, float, int]:
    """Mean, Newey-West t (lag = horizon-1), naive t, n of the daily mean series.

    ⚠ Corrected 2026-09-10 (quant-verifier HIGH). This study's cohorts are PERSISTENT full
    panels, the worst shape for overlap: under H0 the naive t here has sd 3.32 at k=10 and
    4.45 at k=20, so the previously reported "t of 9" at +20d was about 1.9 sigma and was
    never significant. The Newey-West t is the one to read.
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


def main() -> None:  # noqa: C901 - one linear pass: load, benchmark, accumulate, render
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    out_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(_OUT_DIR / f"overhead-supply-study-{datetime.now(tz=UTC).date()}.md")
    )
    frames = asyncio.run(_load(max_stocks=250, min_rows=200))
    print(f"loaded {len(frames)} stocks", file=sys.stderr)

    # observation: (date, overhead, vol, momentum, {k: reached}, {k: fwd_ret})
    obs: list[
        tuple[Any, float, float, float, dict[int, bool], dict[int, bool], dict[int, float]]
    ] = []
    n_ca_dropped = 0
    bench: dict[int, dict[Any, list[float]]] = {k: defaultdict(list) for k in _HORIZONS}

    for _sym, df in frames.items():
        o = df["open"].to_numpy()
        c = df["close"].to_numpy()
        h = df["high"].to_numpy()
        v = df["volume"].to_numpy()
        idx = df.index
        m = len(df)
        if m < _LOOKBACK + max(_HORIZONS) + 2:
            continue
        low = df["low"].to_numpy()
        is_ca = np.concatenate([[0.0], np.abs(np.diff(c) / c[:-1])]) > _CA_JUMP
        rets = np.concatenate([[np.nan], np.diff(c) / c[:-1]])
        vol60 = pd.Series(rets).rolling(60).std(ddof=0).to_numpy()
        for t in range(_LOOKBACK, m - max(_HORIZONS) - 1):
            entry = o[t + 1]  # first tradeable price after the close that defines the band
            if entry <= 0 or np.isnan(vol60[t]):
                continue
            mom12 = (c[t] - c[t - _LOOKBACK]) / c[t - _LOOKBACK]  # ~12m price momentum
            lo, hi = c[t], c[t] * (1 + _TARGET_PCT)
            stop_lvl = c[t] * (1 - _STOP_PCT)
            win_c = c[t - _LOOKBACK : t]
            win_v = v[t - _LOOKBACK : t]
            tot = win_v.sum()
            if tot <= 0:
                continue
            overhead = float(win_v[(win_c > lo) & (win_c <= hi)].sum() / tot)
            reached: dict[int, bool] = {}
            stopped: dict[int, bool] = {}
            fwd: dict[int, float] = {}
            skip = False
            for k in _HORIZONS:
                if bool(is_ca[t + 1 : t + 1 + k].any()):
                    skip = True
                    break
                reached[k] = bool(h[t + 1 : t + 1 + k].max() >= hi)
                stopped[k] = bool(low[t + 1 : t + 1 + k].min() <= stop_lvl)
                r = (c[t + k] - entry) / entry * 100.0
                fwd[k] = r
                bench[k][idx[t + 1]].append(r)
            if skip:
                n_ca_dropped += 1
                continue
            obs.append((idx[t + 1], overhead, float(vol60[t]), float(mom12), reached, stopped, fwd))

    bench_mean = {
        k: {d: statistics.mean(vals) for d, vals in per.items() if vals} for k, per in bench.items()
    }

    if not obs:
        Path(out_path).write_text("# Overhead supply - no observations\n")
        return

    if not obs:
        Path(out_path).write_text("# Overhead supply - no observations\n")
        return
    shares = np.array([o[1] for o in obs])
    cuts = np.quantile(shares, [i / _QUINTILES for i in range(1, _QUINTILES)])

    def q_of(x: float) -> int:
        return int(np.searchsorted(cuts, x, side="right"))

    vols = np.array([o[2] for o in obs])
    moms = np.array([o[3] for o in obs])
    vol_cuts = np.quantile(vols, [1 / 3, 2 / 3])
    mom_cuts = np.quantile(moms, [1 / 3, 2 / 3])

    reach: dict[tuple[int, int], dict[Any, list[float]]] = defaultdict(lambda: defaultdict(list))
    stop_hit: dict[tuple[int, int], dict[Any, list[float]]] = defaultdict(lambda: defaultdict(list))
    ctrl_reach: dict[tuple[str, int, int, int], dict[Any, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    excess: dict[tuple[int, int], dict[Any, list[float]]] = defaultdict(lambda: defaultdict(list))
    # controls: (control name, control tercile, overhead quintile, horizon)
    ctrl: dict[tuple[str, int, int, int], dict[Any, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for date, share, vol, mom, reached, stopped, fwd in obs:
        qi = q_of(share)
        vt = int(np.searchsorted(vol_cuts, vol, side="right"))
        mt = int(np.searchsorted(mom_cuts, mom, side="right"))
        for k in _HORIZONS:
            reach[(qi, k)][date].append(100.0 if reached[k] else 0.0)
            stop_hit[(qi, k)][date].append(100.0 if stopped[k] else 0.0)
            ctrl_reach[("vol60", vt, qi, k)][date].append(100.0 if reached[k] else 0.0)
            ctrl_reach[("mom12", mt, qi, k)][date].append(100.0 if reached[k] else 0.0)
            bm = bench_mean[k].get(date)
            if bm is not None:
                ex = fwd[k] - bm
                excess[(qi, k)][date].append(ex)
                ctrl[("vol60", vt, qi, k)][date].append(ex)
                ctrl[("mom12", mt, qi, k)][date].append(ex)

    lines: list[str] = []
    a = lines.append
    a("# Overhead supply - is the +6% swing target reachable?\n")
    a(
        f"_Generated {datetime.now(tz=UTC).date()} - {len(frames)} liquid stocks - "
        f"window from {_CLEAN_SINCE.date()} - {len(obs):,} stock-days "
        f"({n_ca_dropped:,} dropped for an unadjusted corporate action in the forward "
        f"window)._\n"
    )
    a(
        f"\n`overhead` = share of the trailing {_LOOKBACK}-session traded volume that changed "
        f"hands between today's close and +{_TARGET_PCT * 100:.0f}% above it (the frozen swing "
        "target). Quintile 0 = least trapped supply overhead, 4 = most. Volume is attributed to "
        "each bar's close.\n"
    )
    a(f"\nQuintile cuts: {', '.join(f'{c:.3f}' for c in cuts)}\n")

    a("\n## O-1: P(the +6% target is touched within k sessions) - and its downside twin\n")
    a(
        f"⚠ A reachability gradient is NOT an opportunity gradient. The same volatility that "
        f"makes the +{_TARGET_PCT * 100:.0f}% target easier to touch makes the "
        f"−{_STOP_PCT * 100:.0f}% stop easier to touch too, so `P(stop)` is reported beside it "
        "and the spread between them is the only number that could mean anything. (Neither is "
        "a trade: a real trade stops at whichever comes FIRST, which daily bars cannot "
        "resolve.)\n"
    )
    a("\n| overhead quintile | horizon | n | P(+6% touched) | P(−8% touched) | spread |")
    a("|---|---|---|---|---|---|")
    for k in _HORIZONS:
        for qi in range(_QUINTILES):
            per = reach[(qi, k)]
            n = sum(len(x) for x in per.values())
            p_reach, _tnw, _tn, ndays = _daily_t(per, k)
            pstop, _s1, _s2, _s3 = _daily_t(stop_hit[(qi, k)], k)
            a(
                f"| Q{qi} | +{k}d | {n:,} | {p_reach:.1f}% | {pstop:.1f}% | "
                f"{p_reach - pstop:+.1f}pp |"
            )

    a("\n## O-2: forward excess return, market-demeaned\n")
    a("\n| overhead quintile | horizon | n | mean excess % | t (Newey-West) | naive t |")
    a("|---|---|---|---|---|---|")
    for k in _HORIZONS:
        for qi in range(_QUINTILES):
            per = excess[(qi, k)]
            n = sum(len(x) for x in per.values())
            mean_pct, tstat, naive, ndays = _daily_t(per, k)
            a(
                f"| Q{qi} | +{k}d | {n:,} | {mean_pct:+.3f}% | {tstat:+.2f} ({ndays}d) | "
                f"{naive:+.2f} |"
            )

    a("\n## O-3 (the proxy check): the same gradient WITHIN a control tercile\n")
    a(
        "If `overhead` is only a disguise for volatility or momentum, the Q0-Q4 spread collapses "
        "once the control is held roughly fixed. `spread` = Q0 mean excess - Q4 mean excess at "
        "+10d; the whole-sample spread is the row labelled `(none)`.\n"
    )
    a(f"\nVolatility (60d daily-return sd) terciles at: {vol_cuts[0]:.4f}, {vol_cuts[1]:.4f}")
    a(f"\n12m momentum terciles at: {mom_cuts[0]:+.3f}, {mom_cuts[1]:+.3f}\n")
    a("\n| control | tercile | n | Q0 excess | Q4 excess | spread (Q0-Q4) |")
    a("|---|---|---|---|---|---|")
    k_focus = 10
    q0_all, _, _, _ = _daily_t(excess[(0, k_focus)], k_focus)
    q4_all, _, _, _ = _daily_t(excess[(_QUINTILES - 1, k_focus)], k_focus)
    n_all = sum(len(x) for x in excess[(0, k_focus)].values()) + sum(
        len(x) for x in excess[(_QUINTILES - 1, k_focus)].values()
    )
    a(
        f"| (none) | whole sample | {n_all:,} | {q0_all:+.3f}% | {q4_all:+.3f}% | "
        f"**{q0_all - q4_all:+.3f}%** |"
    )
    for cname, label in (("vol60", "volatility"), ("mom12", "12m momentum")):
        for ti, tname in enumerate(("low", "mid", "high")):
            p0 = ctrl[(cname, ti, 0, k_focus)]
            p4 = ctrl[(cname, ti, _QUINTILES - 1, k_focus)]
            n = sum(len(x) for x in p0.values()) + sum(len(x) for x in p4.values())
            m0, _, _, _ = _daily_t(p0, k_focus)
            m4, _, _, _ = _daily_t(p4, k_focus)
            if n == 0:
                continue
            a(f"| {label} | {tname} | {n:,} | {m0:+.3f}% | {m4:+.3f}% | **{m0 - m4:+.3f}%** |")

    a("\n### O-3b: the proxy check on O-1 too (reachability, not just return)\n")
    a(
        "O-1 is the outcome most mechanically driven by volatility, and Q0 IS the volatile "
        "end. If the reachability gradient is a volatility artefact it should shrink sharply "
        "once volatility is held roughly fixed.\n"
    )
    a("\n| control | tercile | Q0 P(reach) | Q4 P(reach) | spread |")
    a("|---|---|---|---|---|")
    p0a, _, _, _ = _daily_t(reach[(0, k_focus)], k_focus)
    p4a, _, _, _ = _daily_t(reach[(_QUINTILES - 1, k_focus)], k_focus)
    a(f"| (none) | whole sample | {p0a:.1f}% | {p4a:.1f}% | **{p0a - p4a:+.1f}pp** |")
    for cname, label in (("vol60", "volatility"), ("mom12", "12m momentum")):
        for ti, tname in enumerate(("low", "mid", "high")):
            r0 = ctrl_reach[(cname, ti, 0, k_focus)]
            r4 = ctrl_reach[(cname, ti, _QUINTILES - 1, k_focus)]
            if not r0 or not r4:
                continue
            m0, _, _, _ = _daily_t(r0, k_focus)
            m4, _, _, _ = _daily_t(r4, k_focus)
            a(f"| {label} | {tname} | {m0:.1f}% | {m4:.1f}% | **{m0 - m4:+.1f}pp** |")

    a("\n## Reading it\n")
    a(
        "- O-1's `t` is the t of the daily mean HIT RATE, so it tests 'is this rate different "
        "from zero', which is uninteresting on its own. **Read the SPREAD across quintiles**: if "
        "Q0's P(reach) materially exceeds Q4's, overhead supply predicts reachability and is a "
        "candidate veto. If the quintiles are flat, it does not.\n"
        "- O-2 is the profitability side, market-neutral. A monotone gradient there is the "
        "stronger claim.\n"
        "- Neither is a promotion. The bar is t ~ 3.6 on a trade series "
        "(`docs/analysis/dsr-negative-control-2026-09-04.md`).\n"
    )
    Path(out_path).write_text("\n".join(lines))
    print("\n".join(lines))


# Usage:
#     uv run python scripts/overhead_supply_study.py [out.md]


if __name__ == "__main__":
    main()
