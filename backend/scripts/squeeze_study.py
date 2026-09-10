"""Carter's squeeze as a candidate-GENERATION lever: does volatility compression pay?

Generation, not selection, is the open problem: D5 (exit geometry) and D1 (RVOL) were both
tested and refuted on 2026-09-08, so nothing queued attacks profitability. Carter's squeeze
(`Mastering the Trade`, ch11) is the one *generation* idea in `docs/reading/security_analysis/`
that is fully mechanical and computable from daily bars alone.

    "The quiet periods I'm looking for are identified when the Bollinger Bands narrow in width
     to the point where they are actually inside of the Keltner Channels. ... The trade signal
     occurs when the Bollinger Bands then move back outside the Keltner Channels. I use a
     12-period momentum index oscillator to determine whether to go long or short."
     Defaults: Keltner 20 / 1.5, Bollinger 20 / 2.

ONE pre-registered hypothesis. A squeeze FIRE (compression ending) predicts a signed forward
excess return in the momentum oscillator's direction.

MARKET-NEUTRAL BY CONSTRUCTION. A long-biased rule in a rising market looks profitable for
free, and the corpus window is a strong Indian bull market. So every forward return is reduced
by that same day's CROSS-SECTIONAL MEAN forward return over the whole universe, at the same
horizon. What is reported is excess over "hold the average stock that day". Inference is on the
daily mean of that excess across trading days (n = days), never per trade, because forward
windows overlap heavily across both days and stocks.

Also reported: the higher-timeframe alignment filter Carter insists on
("is the hourly firing opposite the weekly? Pass on this trade") in its daily/weekly analogue.
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
import numpy.typing as npt  # noqa: E402
import pandas as pd  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.block_bootstrap import newey_west_t  # noqa: E402
from sqlalchemy import text  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_CLEAN_SINCE = datetime(2023, 7, 3, tzinfo=UTC)
_HORIZONS = (1, 3, 5, 10, 20)
_BB_LEN, _BB_MULT = 20, 2.0
_KC_LEN, _KC_MULT = 20, 1.5
_MOM_LEN = 12
# A close-to-close move this large in a liquid name is a split/bonus, not a trade.
_CA_JUMP = 0.25


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


def _atr(
    h: npt.NDArray[np.float64],
    low: npt.NDArray[np.float64],
    c: npt.NDArray[np.float64],
    n: int,
) -> npt.NDArray[np.float64]:
    """Wilder-family ATR is not needed here - Carter's Keltner default is a simple mean TR."""
    prev = np.concatenate([[np.nan], c[:-1]])
    tr = np.maximum(h - low, np.maximum(np.abs(h - prev), np.abs(low - prev)))
    out: npt.NDArray[np.float64] = pd.Series(tr).rolling(n).mean().to_numpy()
    return out


def _daily_t(per_day: dict[Any, list[float]], horizon: int) -> tuple[float, float, float, int]:
    """Mean, Newey-West t (lag = horizon-1), naive t, and n of the daily mean series.

    Overlap correction added 2026-09-10 (quant-verifier HIGH): consecutive days share
    horizon-1 sessions of the same future, which inflates a naive t. This study's cohorts are
    sparse (~5.5 fires/day) so the correction is small here - but it is printed, not assumed.
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
        else str(_OUT_DIR / f"squeeze-study-{datetime.now(tz=UTC).date()}.md")
    )
    frames = asyncio.run(_load(max_stocks=250, min_rows=200))
    print(f"loaded {len(frames)} stocks", file=sys.stderr)

    # ---- pass 1: the universe benchmark. For each (date, horizon) the cross-sectional mean
    # forward return from that day's open, over every stock that has the data. Squeeze excess
    # is measured against this, so market drift cannot masquerade as edge.
    bench: dict[int, dict[Any, list[float]]] = {k: defaultdict(list) for k in _HORIZONS}
    prepared: dict[str, dict[str, Any]] = {}
    for sym, df in frames.items():
        o = df["open"].to_numpy()
        h = df["high"].to_numpy()
        low = df["low"].to_numpy()
        c = df["close"].to_numpy()
        m = len(df)
        if m < _BB_LEN + max(_HORIZONS) + 40:
            continue
        cs = pd.Series(c)
        ma = cs.rolling(_BB_LEN).mean().to_numpy()
        sd = cs.rolling(_BB_LEN).std(ddof=0).to_numpy()
        bb_u, bb_l = ma + _BB_MULT * sd, ma - _BB_MULT * sd
        atr = _atr(h, low, c, _KC_LEN)
        kc_u, kc_l = ma + _KC_MULT * atr, ma - _KC_MULT * atr
        squeeze = (bb_u < kc_u) & (bb_l > kc_l)
        c2c = np.concatenate([[0.0], np.abs(np.diff(c) / c[:-1])])
        is_ca = c2c > _CA_JUMP
        mom = np.concatenate([[np.nan] * _MOM_LEN, c[_MOM_LEN:] - c[:-_MOM_LEN]])
        # weekly analogue of Carter's higher-timeframe filter: 5x the momentum length.
        # (A weekly BB/KC pair was computed here once and never read - removed 2026-09-10.)
        mom_w = np.concatenate([[np.nan] * (_MOM_LEN * 5), c[_MOM_LEN * 5 :] - c[: -_MOM_LEN * 5]])
        prepared[sym] = {
            "o": o,
            "c": c,
            "idx": df.index,
            "m": m,
            "squeeze": squeeze,
            "mom": mom,
            "is_ca": is_ca,
            "mom_w": mom_w,
        }
        for t in range(1, m - max(_HORIZONS)):
            for k in _HORIZONS:
                if bool(is_ca[t : t + k].any()):
                    continue  # an unadjusted CA is a fake return, not a market move
                bench[k][df.index[t]].append((c[t + k - 1] - o[t]) / o[t] * 100.0)

    bench_mean: dict[int, dict[Any, float]] = {
        k: {d: statistics.mean(v) for d, v in per.items() if v} for k, per in bench.items()
    }

    # ---- pass 2: squeeze fires
    acc: dict[str, dict[int, dict[Any, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    n_fire = 0
    n_long = 0
    n_ca_dropped = 0
    for _sym, p in prepared.items():
        squeeze, mom, o, c, idx, m = p["squeeze"], p["mom"], p["o"], p["c"], p["idx"], p["m"]
        mom_w, is_ca = p["mom_w"], p["is_ca"]
        for t in range(_BB_LEN * 5 + 1, m - max(_HORIZONS) - 1):
            # FIRE on bar t: compression on t-1, gone on t. Entry is the NEXT open (t+1):
            # bar t is only complete at its close, so t+1's open is the first tradeable price
            # (no look-ahead - the same N -> N+1 convention the frozen engine uses).
            if not (squeeze[t - 1] and not squeeze[t]):
                continue
            if np.isnan(mom[t]):
                continue
            direction = 1 if mom[t] > 0 else -1
            entry = o[t + 1]
            if entry <= 0:
                continue
            n_fire += 1
            n_long += 1 if direction > 0 else 0
            date = idx[t + 1]
            aligned = (not np.isnan(mom_w[t])) and (
                (mom_w[t] > 0) if direction > 0 else (mom_w[t] < 0)
            )
            for k in _HORIZONS:
                if bool(is_ca[t + 1 : t + k + 1].any()):
                    n_ca_dropped += 1
                    continue
                raw = direction * (c[t + k] - entry) / entry * 100.0
                bm = bench_mean[k].get(date)
                if bm is None:
                    continue
                excess = raw - direction * bm  # signed: a short earns the negative of drift
                acc["squeeze fire (all)"][k][date].append(excess)
                acc["squeeze fire, long" if direction > 0 else "squeeze fire, short"][k][
                    date
                ].append(excess)
                acc[
                    "squeeze fire + weekly aligned" if aligned else "squeeze fire + weekly opposed"
                ][k][date].append(excess)

    lines: list[str] = []
    a = lines.append
    a("# Carter's squeeze as a generation lever - market-neutral test\n")
    a(
        f"_Generated {datetime.now(tz=UTC).date()} - {len(prepared)} liquid stocks - "
        f"window from {_CLEAN_SINCE.date()} - {n_fire:,} squeeze fires "
        f"({n_long / n_fire * 100:.0f}% long). **{n_ca_dropped:,} fire/horizon observations "
        f"dropped** for an unadjusted corporate action (|close-to-close| > "
        f"{_CA_JUMP * 100:.0f}%) inside the forward window._\n"
    )
    a(
        "\nBB(20,2) inside KC(20,1.5) = compression; the fire is the bar compression ENDS. "
        "Direction from 12-period momentum. Entry at the NEXT session's open (bar t is only "
        "complete at its close). Returns are **excess over that day's cross-sectional mean** at "
        "the same horizon, signed so a short earns the negative of market drift - the corpus "
        "window is a strong bull market and a long-biased rule would otherwise look free. "
        "**`t` is Newey-West at lag k-1 on the daily mean of the excess**; `naive t` is the "
        "uncorrected one. Consecutive days share k-1 sessions of the same future, which "
        "inflates a naive t - small here because fires are sparse (~5.5/day), but shown.\n"
    )
    order = [
        "squeeze fire (all)",
        "squeeze fire, long",
        "squeeze fire, short",
        "squeeze fire + weekly aligned",
        "squeeze fire + weekly opposed",
    ]
    a("\n| cohort | horizon | fires | mean excess % | t (Newey-West) | naive t |")
    a("|---|---|---|---|---|---|")
    for label in order:
        if label not in acc:
            continue
        for k in _HORIZONS:
            per = acc[label][k]
            total = sum(len(v) for v in per.values())
            mean_pct, tstat, naive, ndays = _daily_t(per, k)
            a(
                f"| {label} | +{k}d | {total:,} | {mean_pct:+.3f}% | {tstat:+.2f} ({ndays}d) "
                f"| {naive:+.2f} |"
            )
    a(
        "\n_Reference: the promotion bar for this project is t ~ 3.6 on the trade series "
        "(H8, `docs/analysis/dsr-negative-control-2026-09-04.md`). A t below that is not "
        "evidence of no edge - power is near zero between t 2.6 and 3.5 - but it is not a "
        "promotion either. Record the t._\n"
    )
    Path(out_path).write_text("\n".join(lines))
    print("\n".join(lines))


# Usage:
#     uv run python scripts/squeeze_study.py [out.md]


if __name__ == "__main__":
    main()
