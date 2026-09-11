"""Read-only: measure what five rounds of reviewers ASSUMED — empirical dependence
on the swing corpus, plus the unit/estimand diagnostics they asked for.

SELECT-only. The frozen scorer and the frozen `_simulate_trade` are imported and CALLED,
never reimplemented (W2). Answers, with data:
  Claude Q1  calendar-block bootstrap -> effective n at 3 block lengths
  Claude Q2  pairwise correlation of R across OVERLAPPING trades
  Claude Q4  per-trade outcome in THREE units (R, raw %, return/ATR20)
  Claude Q5  stop-width distribution
  Claude Q7  Delta_select: E[R | top confidence decile] vs E[R | all]
  Claude Q8  is confidence monotone in outcome?
  Claude Q12 panel / signal / gate-passer / trade counts, one denominator chain
  Kimi   Q1  concurrency distribution + the inflation the data actually implies
  Kimi   Q4  defect-#4 frequency (gap-through-stop booked as a WIN)

ROUND 7 (2026-09-11) — the four reviewers converged on the same gap: every round-6 number
is undivided by DIRECTION, and the selection test threw away 84% of the sample. Added:
  R7-A  direction split of every statistic (Claude B / Kimi Catch 2 / ChatGPT / Gemini)
  R7-B  Delta_select as a CONTINUOUS rank statistic on all trades (Claude C / ChatGPT 5 / Kimi)
  R7-C  the level-stage rejects, SIMULATED with fallback stops (Claude D — 61% of gate-passers,
        never once evaluated as a selector)
  R7-D  dependence in PORTFOLIO space, not only R space (ChatGPT 3)
  R7-E  empirical Kelly: max_f E[log(1+fR)], not the binary-bet formula (all four)
  R7-F  winsorization state of every moment + clip count (Claude Q5)
  R7-G  CA-detector strength, and the class mix that explains the sigma gap (Claude A / Kimi Q2)
  R7-I  the 922-day ohlcv_1d hole: which trades are scored across it (mine, round 7)
  R7-J  multivariate stop-width regression - is the gradient geometry or an ATR proxy? (Gemini)

ROUND 8 (2026-09-11) - the external audit recomputed round 7 and found four defects in it.
Added to settle them with measurement rather than argument:
  R8-C1 MDE at 80% power (2.80*SE) beside the t=2 critical effect - 2*SE is 50% power
  R8-C2 the two round-7 splits as INTERACTION tests, not subgroup levels
  R8-C4 the cost-in-R DISTRIBUTION - friction is 1/w, so E[cost] != cost(median w) by Jensen
  R8-C6 HC3 and DATE-CLUSTERED standard errors on the regression that produced t=+3.67
"""
from __future__ import annotations
import argparse, asyncio, collections, math, random, statistics, sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.confluence import run_all_factors, score_from_factors
from app.analysis.risk import compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import swing_levels
from app.backtest.engine import BacktestConfig, BacktestEngine
from app.core.ratios import WINSOR_R, clamp_ratio_f
from app.db.session import AsyncSessionFactory
from app.signals.classifier import classify_signal
from app.services.block_bootstrap import newey_west_t
from app.signals.risk_guards import safe_levels
from app.trading.regime import kaufman_er

WINDOW, SWING_DAYS = 300, 5
# ohlcv_1d carries a 922-day HOLE: 2020-12-23 -> 2023-07-03 (measured 2026-09-11, round 7).
# A 300-bar window that opens before the hole and closes after it computes EMA200/ATR/ADX/pivots
# across a 2.5-year discontinuity as if the two sides were consecutive sessions. 33.2% of the
# round-6 panels are in that state. `--clean-only` restricts the walk to windows wholly on one
# side; the default keeps round 6 reproducible.
GAP_LO, GAP_HI = date(2020, 12, 23), date(2023, 7, 3)
CAPITAL, RISK_PCT = Decimal("100000"), Decimal("2.0")
CA_JUMP = 0.25


async def load_frames(n_stocks: int) -> dict[str, pd.DataFrame]:
    async with AsyncSessionFactory() as db:
        ids = [r[0] for r in (await db.execute(text(
            """SELECT stock_id FROM ohlcv_1d WHERE time > now() - interval '180 days'
               GROUP BY stock_id HAVING count(*) > 100
               ORDER BY percentile_cont(0.5) WITHIN GROUP (ORDER BY close*volume) DESC
               LIMIT :n"""), {"n": n_stocks})).all()]
        rows = (await db.execute(text(
            """SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume
               FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id
               WHERE o.stock_id = ANY(:i) AND o.is_complete
               ORDER BY s.symbol, o.time"""), {"i": ids})).all()
    g: dict[str, list[Any]] = collections.defaultdict(list)
    for r in rows:
        g[r[0]].append(r)
    out: dict[str, pd.DataFrame] = {}
    for sym, rs in g.items():
        if len(rs) < WINDOW + 40:
            continue
        out[sym] = pd.DataFrame(
            {"open": [float(r[2]) for r in rs], "high": [float(r[3]) for r in rs],
             "low": [float(r[4]) for r in rs], "close": [float(r[5]) for r in rs],
             "volume": [float(r[6]) for r in rs]},
            index=pd.to_datetime([r[1] for r in rs]))
    return out


def _as_date(ts: Any) -> date:
    """`TradeRecord.exit_date` is Optional in the frozen dataclass but always set on a
    record that reached an exit; narrow it here rather than sprinkling asserts."""
    if ts is None:
        raise ValueError("trade record reached the outcome stage with no exit_date")
    return ts.date()  # type: ignore[no-any-return]


def atr20(df: pd.DataFrame, i: int) -> float:
    s = df.iloc[max(0, i - 20):i + 1]
    if len(s) < 2:
        return float("nan")
    pc = s["close"].shift(1)
    tr = pd.concat([s["high"] - s["low"], (s["high"] - pc).abs(), (s["low"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.mean())


def pctl(v: list[float], q: float) -> float:
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(q * (len(s) - 1))))]


def describe(v: list[float], label: str, unit: str) -> None:
    if len(v) < 3:
        print(f"  {label:<26} (n<3)"); return
    m, sd = statistics.mean(v), statistics.stdev(v)
    sk = sum(((x - m) / sd) ** 3 for x in v) / len(v) if sd else float("nan")
    ku = sum(((x - m) / sd) ** 4 for x in v) / len(v) - 3 if sd else float("nan")
    print(f"  {label:<26} n={len(v):>5}  mean {m:+8.4f}  med {statistics.median(v):+8.4f}  "
          f"sd {sd:7.4f}  skew {sk:+6.2f}  exkurt {ku:+8.2f}  "
          f"p1 {pctl(v,.01):+7.3f}  p5 {pctl(v,.05):+7.3f}  p95 {pctl(v,.95):+7.3f}  p99 {pctl(v,.99):+7.3f}  [{unit}]")


def calendar_block_bootstrap(
    trades: list[dict[str, Any]], block_days: int, resamples: int = 2000, seed: int = 7
) -> tuple[float, int] | None:
    """Blocks of CALENDAR TIME, not of trades — the unit five rounds argued about."""
    if not trades:
        return None
    days = sorted({t["entry"] for t in trades})
    if len(days) < 10:
        return None
    by_day: dict[date, list[float]] = collections.defaultdict(list)
    for t in trades:
        by_day[t["entry"]].append(t["Rw"])
    span = (days[-1] - days[0]).days or 1
    n_blocks = max(1, math.ceil(span / block_days))
    starts = [days[0] + timedelta(days=k * block_days) for k in range(n_blocks)]
    blocks = []
    for st in starts:
        en = st + timedelta(days=block_days)
        vals = [r for d, rs in by_day.items() if st <= d < en for r in rs]
        if vals:
            blocks.append(vals)
    if len(blocks) < 5:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        draw: list[float] = []
        while len(draw) < len(trades):
            draw.extend(rng.choice(blocks))
        means.append(statistics.mean(draw[:len(trades)]))
    se = statistics.stdev(means)
    return se, len(blocks)



# ---------------------------------------------------------------- ROUND 7 helpers

def spearman(xs: list[float], ys: list[float]) -> float:
    """Rank correlation. Ties averaged, so a confidence scale with heavy ties is honest."""
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda k: v[k])
        r = [0.0] * len(v)
        k = 0
        while k < len(order):
            j = k
            while j + 1 < len(order) and v[order[j + 1]] == v[order[k]]:
                j += 1
            avg = (k + j) / 2.0 + 1.0
            for t in range(k, j + 1):
                r[order[t]] = avg
            k = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def perm_p(xs: list[float], ys: list[float], stat: float, n: int = 5000, seed: int = 11) -> float:
    """Two-sided permutation p for a rank statistic. No distributional assumption."""
    rng = random.Random(seed)
    ys2 = list(ys)
    hits = 0
    for _ in range(n):
        rng.shuffle(ys2)
        if abs(spearman(xs, ys2)) >= abs(stat):
            hits += 1
    return (hits + 1) / (n + 1)


def ols_slope(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Slope of y on x with iid SE. Returns (slope, se, t)."""
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0 or n < 3:
        return float("nan"), float("nan"), float("nan")
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - a - b * x for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / (n - 2)
    se = math.sqrt(s2 / sxx)
    return b, se, (b / se if se else float("nan"))


def moments(v: list[float]) -> tuple[int, float, float, float, float, float]:
    """n, mean, sd, se, skew, excess kurtosis."""
    n = len(v)
    if n < 3:
        return n, float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
    m, sd = statistics.mean(v), statistics.stdev(v)
    sk = sum(((x - m) / sd) ** 3 for x in v) / n if sd else float("nan")
    ku = sum(((x - m) / sd) ** 4 for x in v) / n - 3 if sd else float("nan")
    return n, m, sd, sd / math.sqrt(n), sk, ku


def report_group(label: str, v: list[float]) -> None:
    n, m, sd, se, sk, ku = moments(v)
    if n < 3:
        print(f"  {label:<18} n={n:>4}  (n<3)"); return
    win = 100 * sum(1 for x in v if x > 0) / n
    print(f"  {label:<18} n={n:>4}  mean {m:+8.4f}  sd {sd:6.3f}  SE {se:6.4f}  "
          f"t {m/se if se else float('nan'):+6.2f}  win {win:5.1f}%  med {statistics.median(v):+7.3f}")


def kelly_empirical(rs: list[float]) -> tuple[float, float]:
    """max_f E[log(1 + f*R)] on the ACTUAL distribution, with R in units of risk.

    A binary-bet f* = p - q/b is the wrong instrument for a continuous, barrier-truncated,
    time-capped payoff (all four reviewers, round 7). Grid search is exact enough: the
    objective is concave in f and f is bounded below by the worst loss.
    """
    worst = min(rs)
    hi = 0.999 / abs(worst) if worst < 0 else 5.0
    best_f, best_g = 0.0, 0.0
    f = 0.0
    while f <= hi:
        g = 0.0
        ok = True
        for r in rs:
            x = 1.0 + f * r
            if x <= 1e-9:
                ok = False
                break
            g += math.log(x)
        if ok:
            g /= len(rs)
            if g > best_g:
                best_f, best_g = f, g
        f += hi / 400.0
    return best_f, best_g


def ols_multi(
    y: list[float], X: list[list[float]], names: list[str],
    clusters: list[Any] | None = None,
) -> None:
    """Multivariate OLS with iid SEs, printed as a table. Gemini's R7-J ask: does the
    stop-width gradient survive controls for ATR%, relative volume and price level, or is it
    a proxy for volatility? Normal equations with a pseudo-inverse, so a collinear column
    degrades rather than raising.
    """
    A = np.column_stack([np.ones(len(y))] + [np.asarray(c, dtype=float) for c in X])
    yv = np.asarray(y, dtype=float)
    ok = np.isfinite(A).all(axis=1) & np.isfinite(yv)
    A, yv = A[ok], yv[ok]
    n, k = A.shape
    if n <= k + 2:
        print("    (too few complete rows)"); return
    beta, *_ = np.linalg.lstsq(A, yv, rcond=None)
    resid = yv - A @ beta
    s2 = float(resid @ resid) / (n - k)
    xtx_inv = np.linalg.pinv(A.T @ A)
    se_iid = np.sqrt(np.diag(s2 * xtx_inv))

    # R8-C6: an iid OLS SE is the WRONG quantity here, not an approximation. The dependent
    # variable has excess kurtosis +8.19, the observations OVERLAP (mean concurrency 2.08), and
    # RVOL is strongly date-clustered because market-wide volume spikes hit every name on the
    # same day. HC3 prices the tail; clustering by entry date prices the common daily component.
    h = np.einsum("ij,jk,ik->i", A, xtx_inv, A)          # leverages
    u3 = resid / np.clip(1.0 - h, 1e-9, None)            # HC3 weighting
    meat3 = (A * u3[:, None]).T @ (A * u3[:, None])
    se_hc3 = np.sqrt(np.diag(xtx_inv @ meat3 @ xtx_inv))

    se_cl = None
    if clusters is not None:
        cl = [c for c, keep in zip(clusters, ok) if keep]
        meat = np.zeros((k, k))
        by: dict[Any, list[int]] = collections.defaultdict(list)
        for i2, c in enumerate(cl):
            by[c].append(i2)
        for rows in by.values():
            sg = (A[rows] * resid[rows][:, None]).sum(axis=0)
            meat += np.outer(sg, sg)
        g = len(by)
        if g > k + 1:
            adj = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
            se_cl = np.sqrt(np.diag(xtx_inv @ (adj * meat) @ xtx_inv))

    r2 = 1 - float(resid @ resid) / float(((yv - yv.mean()) ** 2).sum())
    ncl = len(set(c for c, keep in zip(clusters, ok) if keep)) if clusters is not None else 0
    print(f"    n={n}  R2={r2:.4f}" + (f"  clusters={ncl}" if clusters is not None else ""))
    print(f"      {'regressor':<16} {'beta':>10}  {'SE(iid)':>9} {'t':>6} | "
          f"{'SE(HC3)':>9} {'t':>6} | {'SE(clust)':>9} {'t':>6}")
    for j, nm in enumerate(["intercept"] + names):
        b = beta[j]
        row = f"      {nm:<16} {b:+10.5f}  {se_iid[j]:9.5f} {b/se_iid[j]:+6.2f} | " \
              f"{se_hc3[j]:9.5f} {b/se_hc3[j]:+6.2f} | "
        row += f"{se_cl[j]:9.5f} {b/se_cl[j]:+6.2f}" if se_cl is not None else f"{'-':>9} {'-':>6}"
        print(row)


def simulate_rejects(
    rejects: list[dict[str, Any]], frames: dict[str, pd.DataFrame],
    engine: BacktestEngine, rule: str,
) -> list[dict[str, Any]]:
    """Claude Finding D: the level stage kills 61% of gate-passing swing panels on pivot
    proximity, which SS4.4 says is anti-correlated with outcome. Nobody has ever simulated the
    rejected cohort. Replace the pivot stop with a fallback and measure it on identical panels.
    """
    out = []
    for rj in rejects:
        df = frames.get(rj["sym"])
        if df is None:
            continue
        i = rj["i"]
        stop_bar = i + 1 + SWING_DAYS
        if stop_bar >= len(df):
            continue
        entry = rj["entry"]
        if rule == "flat5":
            dist = entry * 0.05
        else:
            a = atr20(df, i)
            if not a or a != a:
                continue
            dist = 2.0 * a
        if dist <= 0:
            continue
        buy = rj["dir"] == "BUY"
        stop = entry - dist if buy else entry + dist
        target = entry + 3 * dist if buy else entry - 3 * dist
        if stop <= 0:
            continue
        qty = volatility_adjusted_qty(
            compute_quantity(CAPITAL, RISK_PCT, Decimal(str(entry)), Decimal(str(stop))),
            df.iloc[i - WINDOW + 1:i + 1])
        if not qty:
            continue
        closes = df["close"]
        seg = closes.iloc[max(0, i - 1):stop_bar + 1]
        if (seg.pct_change().abs().dropna() > CA_JUMP).any():
            continue
        flags = [False] * len(df)
        flags[stop_bar] = True
        rec = engine._simulate_trade(  # noqa: SLF001
            rj["sym"], i, rj["dir"], "swing", rj["conf"],
            stop, target, qty, df, flags)
        if rec is None or rec.pnl_pct is None:
            continue
        w_pct = abs(rec.entry_price - stop) / rec.entry_price * 100
        if w_pct <= 0:
            continue
        R = float(rec.pnl_pct) / w_pct
        out.append({"sym": rj["sym"], "entry": df.index[i + 1].date(), "exit": _as_date(rec.exit_date),
                    "R": R, "Rw": clamp_ratio_f(R, WINSOR_R), "w": w_pct, "dir": rj["dir"],
                    "conf": rj["conf"], "ret_pct": float(rec.pnl_pct)})
    return out


def _key_decomp(factors: list[Any]) -> dict[str, float]:
    """ROUND 9 / Kimi C3 — three rival ranking keys from the SAME frozen factor list.

    `wsum`   raw weighted sum, UNNORMALIZED (what confidence divides)
    `nsc`    breadth: how many factors actually scored
    `wsc`    the denominator itself (weight of scoring factors)
    `top`    concentration: the largest single |w*s| as a share of the total
    Read-only on the frozen scorer's output — nothing is recomputed or reimplemented.
    """
    contrib = [(f.weight * f.score) for f in factors if f.score != 0.0]
    tot = sum(abs(c) for c in contrib)
    return {
        "wsum": sum(f.weight * f.score for f in factors),
        "nsc": float(len(contrib)),
        "wsc": sum(f.weight for f in factors if f.score != 0.0),
        "top": (max((abs(c) for c in contrib), default=0.0) / tot) if tot else float("nan"),
    }


def basket_series(frames: dict[str, pd.DataFrame]) -> dict[date, float]:
    """ROUND 9 / G5 — the equal-weight eligible-universe daily return, as ONE owner.

    §12.20 computed this with an ad-hoc query and then used it as a fixed-horizon
    scalar (+0.0816%/day). Every reviewer that read round 8 asked for the same thing:
    the null a trade must beat is the basket over THAT TRADE'S OWN window, paired, not
    a horizon average. Built from the frames already in memory — same universe
    definition as `load_frames`, so it inherits the same (documented) 0a.3 survivorship
    bias and no new query.
    """
    acc: dict[date, list[float]] = collections.defaultdict(list)
    for df in frames.values():
        r = df["close"].pct_change()
        for ts, v in r.items():
            if v == v:
                acc[ts.date()].append(float(v))
    return {d: statistics.mean(v) for d, v in acc.items() if v}


def basket_window(bser: dict[date, float], d0: date, d1: date) -> tuple[float, int]:
    """Compounded basket return over (d0, d1] in %, and the session count = holding period.

    The session count IS `T`: the probe caps at SWING_DAYS but trades exit early at a
    barrier, so mean T is strictly less than the cap and has never been emitted.
    """
    if d1 <= d0:
        return 0.0, 0
    c, n = 1.0, 0
    for d in sorted(bser):
        if d0 < d <= d1:
            c *= 1.0 + bser[d]
            n += 1
    return (c - 1.0) * 100.0, n


async def main(n_stocks: int, stride: int, clean_only: bool = False,
               dump: str | None = None) -> None:
    frames = await load_frames(n_stocks)
    print(f"names with usable history: {len(frames)}   (stride {stride}, clean_only={clean_only})")
    bser = basket_series(frames)
    print(f"basket sessions: {len(bser)}  mean daily {100*statistics.mean(bser.values()):+.4f}%")
    engine = BacktestEngine(BacktestConfig(capital=CAPITAL, risk_pct=RISK_PCT))

    panels = gate_pass = swing_cls = lvl_reject = 0
    dirs: collections.Counter[str] = collections.Counter()
    cls_mix: collections.Counter[str] = collections.Counter()
    dir_by_stage: collections.Counter[str] = collections.Counter()
    trades: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    ca_drop = defect4 = ca_soft = straddle_skip = 0

    for sym, df in frames.items():
        closes = df["close"]
        for i in range(WINDOW, len(df) - SWING_DAYS - 2, stride):
            window = df.iloc[i - WINDOW + 1:i + 1]
            straddles = (window.index[0].date() <= GAP_LO and window.index[-1].date() >= GAP_HI)
            if clean_only and straddles:
                straddle_skip += 1
                continue
            panels += 1
            factors = run_all_factors(window, "1d")
            res = score_from_factors(factors, window, 70)
            if res is None:
                continue
            gate_pass += 1
            dirs[res.direction] += 1
            cls = classify_signal("1d", res.factors, res.is_multibagger)
            cls_mix[cls] += 1
            if cls != "swing":
                continue
            swing_cls += 1
            dir_by_stage[f"swing:{res.direction}"] += 1
            entry = Decimal(str(closes.iloc[i]))
            low, high = swing_levels(window)
            lv = safe_levels(res.direction, "swing", entry, low, high, None)
            if lv is None:
                lvl_reject += 1
                rejects.append({"sym": sym, "i": i, "dir": res.direction,
                                "conf": res.confidence_pct, "entry": float(entry)})
                continue
            stop, target = lv
            qty = volatility_adjusted_qty(compute_quantity(CAPITAL, RISK_PCT, entry, stop), window)
            if not qty:
                continue
            stop_bar = i + 1 + SWING_DAYS
            if stop_bar >= len(df):
                continue
            seg = closes.iloc[max(0, i - 1):stop_bar + 1]
            if (seg.pct_change().abs().dropna() > CA_JUMP).any():
                ca_drop += 1
                continue
            flags = [False] * len(df)
            flags[stop_bar] = True
            rec = engine._simulate_trade(  # noqa: SLF001
                sym, i, res.direction, "swing", res.confidence_pct,
                float(stop), float(target), qty, df, flags)
            if rec is None or rec.pnl_pct is None:
                continue
            w_pct = abs(rec.entry_price - float(stop)) / rec.entry_price * 100
            if w_pct <= 0:
                continue
            R = float(rec.pnl_pct) / w_pct
            # defect #4: booked as hit_sl but the trade made money
            if rec.hit_sl and float(rec.pnl_pct) > 0:
                defect4 += 1
            a = atr20(df, i)
            vols = df["volume"].iloc[max(0, i - 20):i + 1]
            vmean = float(vols.mean()) if len(vols) else float("nan")
            sgn = 1.0 if res.direction == "BUY" else -1.0
            seg_soft = closes.iloc[max(0, i - WINDOW + 1):stop_bar + 1]
            if (seg_soft.pct_change().abs().dropna() > 0.08).any():
                ca_soft += 1
            _entry_d, _exit_d = df.index[i + 1].date(), _as_date(rec.exit_date)
            _bench, _T = basket_window(bser, _entry_d, _exit_d)
            _er = kaufman_er([float(x) for x in closes.iloc[max(0, i - 20):i + 1]])
            trades.append({
                "sym": sym, "entry": _entry_d, "exit": _exit_d,
                # ROUND 9 — the three columns every round-8 reviewer converged on.
                # T: the probe caps at SWING_DAYS but exits early; mean T was never emitted,
                #    and every per-day / drift-null statement is conditional on it.
                # bench/excess: the PAIRED drift null (G5) — this trade's own window, not a
                #    fixed-horizon scalar. Also removes the drift*T term from the stop-width
                #    family, which re-reporting in raw % does NOT remove (C2/C3).
                # er: the deployed display path drops ER < 0.30 and the corpus never did,
                #    so the offered set is narrower than the corpus along an untested axis.
                "T": _T, "bench": _bench, "excess": float(rec.pnl_pct) - _bench,
                "er": _er if _er is not None else float("nan"),
                # ROUND 9 / Kimi C3 — the confidence NORMALIZER, decomposed.
                # confluence.py:160 divides by the weight of factors that SCORED, so one
                # 0.8 factor reads 80% while four moderate agreeing factors read ~50%: the
                # key the UI sorts by mechanically rewards SPARSE conviction. rho(conf, R)
                # = -0.018 may therefore be the normalizer's fault rather than the factors'.
                # These four columns let the same panels be re-ranked by three rival keys.
                **_key_decomp(res.factors),
                "R": R, "Rw": clamp_ratio_f(R, WINSOR_R), "w": w_pct,
                "ret_pct": float(rec.pnl_pct), "conf": res.confidence_pct,
                "dir": res.direction, "qty": qty, "entry_px": rec.entry_price,
                "straddle": straddles,
                "atr_pct": (a / rec.entry_price * 100) if a and a == a and rec.entry_price else float("nan"),
                "rvol": (float(df["volume"].iloc[i]) / vmean) if vmean and vmean == vmean and vmean > 0 else float("nan"),
                "log_close": math.log(rec.entry_price) if rec.entry_price > 0 else float("nan"),
                "cash": float(rec.pnl_pct) / 100.0 * rec.entry_price * qty,
                "ret_atr": (float(rec.pnl_pct) / 100 * rec.entry_price / a) if a and a == a else float("nan"),
            })
            _ = sgn

    print(f"\n== Claude Q12: the denominator chain (ONE definition each) ==")
    print(f"  panels scored (a name x a decision bar, {WINDOW}-bar window)  : {panels:,}")
    print(f"  ... clearing the >=70% confluence gate                        : {gate_pass:,} ({100*gate_pass/max(panels,1):.2f}%)")
    print(f"      direction split                                           : {dict(dirs)}")
    print(f"  ... classified SWING                                          : {swing_cls:,}")
    print(f"  ... rejected at the level stage (cap/wrong-side/degenerate)   : {lvl_reject:,}")
    print(f"  ... dropped as unadjusted corporate actions (|move|>25%)      : {ca_drop:,}")
    print(f"  ... RESOLVED TRADES                                           : {len(trades):,}")

    # ROUND 9: write the artifact FIRST. One expensive pass produces the per-trade table;
    # every cell, contrast and unit-change downstream is then a cheap read off the file
    # (Kimi R4). Emitted before the report sections so a small-n run still yields the dump.
    if dump:
        import csv
        cols = ["sym", "entry", "exit", "T", "dir", "w", "R", "Rw", "ret_pct", "ret_atr",
                "bench", "excess", "cash", "conf", "er", "straddle", "atr_pct", "rvol",
                "log_close", "entry_px", "qty", "wsum", "nsc", "wsc", "top"]
        with open(dump, "w", newline="") as fh:
            wtr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            wtr.writeheader()
            wtr.writerows(trades)
        print(f"== round 9: dumped {len(trades)} trades x {len(cols)} cols -> {dump} ==")

    if not trades:
        return

    print(f"\n== Kimi Q4: defect-#4 frequency (hit_sl booked with a POSITIVE return) ==")
    print(f"  {defect4} of {len(trades)} trades ({100*defect4/len(trades):.2f}%)")

    print(f"\n== Claude Q4: the SAME trades in THREE units ==")
    describe([t["Rw"] for t in trades], "R (winsorized +/-10)", "R")
    describe([t["R"] for t in trades],  "R (raw)", "R")
    describe([t["ret_pct"] for t in trades], "raw return", "%")
    describe([t["ret_atr"] for t in trades if t["ret_atr"] == t["ret_atr"]], "return / ATR20-at-entry", "ATR")

    print(f"\n== Claude Q5: stop-width distribution (the R denominator) ==")
    w = [t["w"] for t in trades]
    if len(w) < 3:
        print("  (n<3)")
        return
    print(f"  mean {statistics.mean(w):.2f}%  sd {statistics.stdev(w):.2f}  "
          f"p5 {pctl(w,.05):.2f}%  p50 {statistics.median(w):.2f}%  p95 {pctl(w,.95):.2f}%  "
          f"CV {statistics.stdev(w)/statistics.mean(w):.2f}")

    print(f"\n== Kimi Q1: CONCURRENCY actually observed ==")
    span_days: collections.Counter[date] = collections.Counter()
    for t in trades:
        d = t["entry"]
        while d <= t["exit"]:
            span_days[d] += 1
            d = d + timedelta(days=1)
    occ = sorted(span_days.values())
    if occ:
        print(f"  open positions per calendar day: mean {statistics.mean(occ):.2f}  "
              f"median {statistics.median(occ)}  p95 {pctl([float(x) for x in occ],.95):.0f}  max {max(occ)}")

    print(f"\n== Claude Q1: CALENDAR-block bootstrap -> the effective n nobody measured ==")
    Rw = [t["Rw"] for t in trades]
    if len(Rw) < 3:
        return
    sd_R = statistics.stdev(Rw)
    se_iid = sd_R / math.sqrt(len(Rw))
    print(f"  sigma_R {sd_R:.4f}   iid SE {se_iid:.4f}   nominal n {len(Rw)}")
    for bd in (10, 30, 60):
        r = calendar_block_bootstrap(trades, bd)
        if r is None:
            print(f"  block {bd:>2}d: not assessable"); continue
        se, nb = r
        infl = (se / se_iid) ** 2
        print(f"  block {bd:>2}d ({nb:>3} blocks): SE {se:.4f}  inflation {infl:5.2f}x  "
              f"=> EFFECTIVE n {len(Rw)/infl:7.0f}   MDE@t2 {2*sd_R/math.sqrt(len(Rw)/infl):+.4f}R")

    print(f"\n== Claude Q2: pairwise correlation of R across OVERLAPPING trades ==")
    idx = sorted(range(len(trades)), key=lambda k: trades[k]["entry"])
    pairs: list[tuple[float, float]] = []
    for a in range(len(idx)):
        ta = trades[idx[a]]
        for b in range(a + 1, min(a + 400, len(idx))):
            tb = trades[idx[b]]
            if tb["entry"] > ta["exit"]:
                break
            pairs.append((ta["Rw"], tb["Rw"]))
    if len(pairs) > 30:
        xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((x-mx)*(y-my) for x, y in pairs)
        den = math.sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
        print(f"  overlapping pairs {len(pairs):,}   MEASURED rho_bar = {num/den if den else float('nan'):+.4f}")
        print(f"  (the document ASSUMES 0.50 everywhere)")
    else:
        print("  too few overlapping pairs")

    print(f"\n== Claude Q8 / Q7: is CONFIDENCE monotone in outcome, and what is Delta_select? ==")
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    for t in trades:
        c = t["conf"]
        k = "70-74" if c < 75 else "75-79" if c < 80 else "80-84" if c < 85 else "85-89" if c < 90 else "90+"
        buckets[k].append(t["Rw"])
    for k in ("70-74", "75-79", "80-84", "85-89", "90+"):
        v = buckets.get(k, [])
        if v:
            print(f"  confidence {k:<7} n={len(v):>5}  mean R {statistics.mean(v):+.4f}  "
                  f"median {statistics.median(v):+.3f}  win {100*sum(1 for x in v if x>0)/len(v):5.1f}%")
    cut = pctl([float(t["conf"]) for t in trades], 0.90)
    top = [t["Rw"] for t in trades if t["conf"] >= cut]
    if len(top) > 20:
        d = statistics.mean(top) - statistics.mean(Rw)
        se_d = math.sqrt(statistics.stdev(top)**2/len(top) + sd_R**2/len(Rw))
        print(f"  Delta_select (top decile, conf>={cut:.0f}, n={len(top)}) = {d:+.4f}R  "
              f"SE {se_d:.4f}  t {d/se_d if se_d else float('nan'):+.2f}")

    # =============================== ROUND 7 ===============================
    print("\n" + "=" * 78)
    print("ROUND 7 — the four reviewers' converging questions")
    print("=" * 78)

    print("\n== R7-G: class mix of gate-passers (the sigma_R reconciliation) ==")
    print(f"  {dict(cls_mix)}")
    print(f"  direction at gate    : {dict(dirs)}")
    print(f"  direction at swing   : {dict(dir_by_stage)}")
    dtr: collections.Counter[str] = collections.Counter(t["dir"] for t in trades)
    print(f"  direction in TRADES  : {dict(dtr)}")

    print("\n== R7-I: the 922-day DATA HOLE (2020-12-23 -> 2023-07-03), measured ==")
    print(f"  panels skipped as gap-straddling (clean_only={clean_only}): {straddle_skip:,}")
    st = [t for t in trades if t.get("straddle")]
    cl = [t for t in trades if not t.get("straddle")]
    print(f"  trades on a gap-STRADDLING window : {len(st)} ({100*len(st)/max(len(trades),1):.1f}%)")
    print(f"  trades on a CLEAN window          : {len(cl)}")
    report_group("straddling", [t["Rw"] for t in st])
    report_group("clean", [t["Rw"] for t in cl])
    for lbl, sub in (("straddling", st), ("clean", cl)):
        if len(sub) > 2:
            print(f"    {lbl:<12} sigma_R {statistics.stdev([t['Rw'] for t in sub]):.4f}  "
                  f"stop width med {statistics.median([t['w'] for t in sub]):.2f}%")

    print("\n== R7-A: DIRECTION SPLIT — every headline, divided ==")
    for unit, key in (("R (winsorized)", "Rw"), ("R (raw)", "R"), ("raw return %", "ret_pct")):
        print(f"  --- {unit}")
        report_group("ALL", [t[key] for t in trades])
        for d in ("BUY", "SELL"):
            report_group(d, [t[key] for t in trades if t["dir"] == d])
    print("  --- stop width % by direction")
    for d in ("BUY", "SELL"):
        wv = [t["w"] for t in trades if t["dir"] == d]
        if len(wv) > 2:
            print(f"    {d:<5} n={len(wv):>4}  mean {statistics.mean(wv):.2f}%  med {statistics.median(wv):.2f}%")

    print("\n== R7-A2: calendar-block bootstrap, BUY-only (the tradeable book) ==")
    buys = [t for t in trades if t["dir"] == "BUY"]
    if len(buys) > 20:
        bR = [t["Rw"] for t in buys]
        sdb = statistics.stdev(bR)
        se_i = sdb / math.sqrt(len(bR))
        print(f"  sigma_R {sdb:.4f}  iid SE {se_i:.4f}  n {len(bR)}  mean {statistics.mean(bR):+.4f}  t {statistics.mean(bR)/se_i:+.2f}")
        for bd in (10, 30):
            r = calendar_block_bootstrap(buys, bd)
            if r:
                se, nb = r
                print(f"  block {bd:>2}d ({nb:>3}): SE {se:.4f}  inflation {(se/se_i)**2:5.2f}x  "
                      f"MDE@t2 {2*sdb/math.sqrt(len(bR)/((se/se_i)**2)):+.4f}R")

    print("\n== R7-B: Delta_select as a CONTINUOUS statistic (uses ALL trades, not the top decile) ==")
    for label, sub in (("ALL", trades), ("BUY only", [t for t in trades if t["dir"] == "BUY"]),
                       ("SELL only", [t for t in trades if t["dir"] == "SELL"])):
        if len(sub) < 20:
            print(f"  {label:<10} n={len(sub)} (too few)"); continue
        cs = [float(t["conf"]) for t in sub]
        rs = [t["Rw"] for t in sub]
        rho = spearman(cs, rs)
        slope, slope_se, slope_t = ols_slope(cs, rs)
        p_perm = perm_p(cs, rs, rho)
        print(f"  {label:<10} n={len(sub):>4}  spearman rho {rho:+.4f}  perm p {p_perm:.4f}  "
              f"| OLS slope {slope:+.5f}R/conf-pt  SE {slope_se:.5f}  t {slope_t:+.2f}  "
              f"90% CI [{slope - 1.645 * slope_se:+.5f},{slope + 1.645 * slope_se:+.5f}]")
        print(f"             detectable rho at t=2 with this n: {2/math.sqrt(len(sub)-1):.3f}")

    print("\n== R7-B2: direction x confidence cross-tab (Kimi Q7 — is 80-84 a shorts artifact?) ==")
    def bkt(c: int) -> str:
        return "70-74" if c < 75 else "75-79" if c < 80 else "80-84" if c < 85 else "85-89" if c < 90 else "90+"
    print(f"  {'bucket':<8} {'BUY n':>6} {'BUY meanR':>10} {'SELL n':>7} {'SELL meanR':>11}")
    for k in ("70-74", "75-79", "80-84", "85-89", "90+"):
        row = []
        for d in ("BUY", "SELL"):
            v = [t["Rw"] for t in trades if t["dir"] == d and bkt(t["conf"]) == k]
            row.append((len(v), statistics.mean(v) if v else float("nan")))
        print(f"  {k:<8} {row[0][0]:>6} {row[0][1]:>+10.4f} {row[1][0]:>7} {row[1][1]:>+11.4f}")

    print("\n== R7-C: the LEVEL-STAGE REJECTS, simulated with a fallback stop ==")
    print(f"  rejected panels available: {len(rejects)}")
    for rule, name in (("flat5", "flat 5% stop"), ("atr2", "2 x ATR20 stop")):
        rj = simulate_rejects(rejects, frames, engine, rule)
        if not rj:
            print(f"  {name:<16}: no simulable rejects"); continue
        print(f"  --- {name} (n={len(rj)})")
        report_group("rejects ALL", [t["Rw"] for t in rj])
        for d in ("BUY", "SELL"):
            report_group(f"rejects {d}", [t["Rw"] for t in rj if t["dir"] == d])
        wv = [t["w"] for t in rj]
        print(f"    stop width: mean {statistics.mean(wv):.2f}%  med {statistics.median(wv):.2f}%")
        # paired by date against the accepted cohort
        acc_by_day: dict[Any, list[float]] = collections.defaultdict(list)
        for t in trades:
            acc_by_day[t["entry"]].append(t["Rw"])
        rej_by_day: dict[Any, list[float]] = collections.defaultdict(list)
        for t in rj:
            rej_by_day[t["entry"]].append(t["Rw"])
        common = sorted(set(acc_by_day) & set(rej_by_day))
        if len(common) > 5:
            dif = [statistics.mean(rej_by_day[d]) - statistics.mean(acc_by_day[d]) for d in common]
            n2, m2, sd2, se2, _, _ = moments(dif)
            print(f"    PAIRED by entry date: {n2} shared days  "
                  f"mean(reject - accept) {m2:+.4f}R  SE {se2:.4f}  t {m2/se2 if se2 else float('nan'):+.2f}")

    print("\n== R7-D: dependence in PORTFOLIO space, not only R space (ChatGPT item 3) ==")
    idx2 = sorted(range(len(trades)), key=lambda k: trades[k]["entry"])
    prs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for a in range(len(idx2)):
        ta = trades[idx2[a]]
        for b in range(a + 1, min(a + 400, len(idx2))):
            tb = trades[idx2[b]]
            if tb["entry"] > ta["exit"]:
                break
            prs.append((ta, tb))
    def corr_on(key: str) -> float:
        xs = [p[0][key] for p in prs]; ys = [p[1][key] for p in prs]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        return num / den if den else float("nan")
    if len(prs) > 30:
        print(f"  overlapping pairs {len(prs):,}")
        for key, name in (("Rw", "R (winsorized)"), ("ret_pct", "raw return %"), ("cash", "cash P&L (Rs)")):
            print(f"    rho_bar on {name:<18} {corr_on(key):+.4f}")
        # downside co-occurrence: P(both lose) vs P(lose)^2
        pl = sum(1 for t in trades if t["Rw"] < 0) / len(trades)
        both = sum(1 for a, b in prs if a["Rw"] < 0 and b["Rw"] < 0) / len(prs)
        print(f"    P(lose) {pl:.3f}  P(lose)^2 {pl*pl:.3f}  P(both lose | overlap) {both:.3f}  "
              f"lift {both/(pl*pl) if pl else float('nan'):.3f}x")
        sd_pair = statistics.stdev([p[0]["cash"] for p in prs])
        print(f"    (cash sd across pair-firsts Rs{sd_pair:,.0f} — sizing is risk-first so cash sd is NOT constant)")

    print("\n== R7-E: EMPIRICAL Kelly — max_f E[log(1+fR)], not p - q/b ==")
    kelly_sets: list[tuple[str, list[float]]] = [
        ("ALL gross", [float(t["Rw"]) for t in trades]),
        ("BUY gross", [float(t["Rw"]) for t in trades if t["dir"] == "BUY"]),
        ("ALL net(-0.111R)", [float(t["Rw"]) - 0.111 for t in trades]),
        ("BUY net(-0.111R)", [float(t["Rw"]) - 0.111 for t in trades if t["dir"] == "BUY"]),
    ]
    for label, ks in kelly_sets:
        if len(ks) < 20:
            continue
        f_star, g = kelly_empirical(ks)
        mu, sg = statistics.mean(ks), statistics.stdev(ks)
        print(f"  {label:<18} n={len(ks):>4}  mean {mu:+.4f}  f*(empirical) {f_star:.4f}  "
              f"E[log] {g:+.6f}  | mu/sigma^2 {mu/(sg*sg):+.4f}")
        rng = random.Random(3)
        bs = []
        for _ in range(2000):
            samp = [ks[rng.randrange(len(ks))] for _ in range(len(ks))]
            bs.append(statistics.mean(samp) / (statistics.stdev(samp) ** 2))
        bs.sort()
        print(f"                     mu/sigma^2 bootstrap 90% CI [{bs[100]:+.4f}, {bs[1899]:+.4f}]")

    print("\n== R7-F: WINSORIZATION state of every round-6 moment ==")
    clipped = sum(1 for t in trades if abs(t["R"]) > WINSOR_R)
    print(f"  clipped at +/-{WINSOR_R:.0f}R: {clipped} of {len(trades)} ({100*clipped/len(trades):.2f}%)")
    for label, v in (("R winsorized", [t["Rw"] for t in trades]), ("R raw", [t["R"] for t in trades]),
                     ("raw return %", [t["ret_pct"] for t in trades]),
                     ("return/ATR20", [t["ret_atr"] for t in trades if t["ret_atr"] == t["ret_atr"]])):
        n, m, sd, se, sk, ku = moments(v)
        print(f"  {label:<14} n={n:>4}  mean {m:+8.4f}  sd {sd:7.4f}  skew {sk:+6.2f}  exkurt {ku:+8.2f}")

    print("\n== R7-G2: CA-detector strength (Claude Q6 — 1 event in 185 windows: clean, or blind?) ==")
    print(f"  hard drops, |1d move| > {CA_JUMP*100:.0f}% inside the trade window : {ca_drop}")
    print(f"  soft flags, |1d move| >  8% inside the 300-bar SCORING window: {ca_soft} of {len(trades)} trades "
          f"({100*ca_soft/max(len(trades),1):.1f}%)")
    print("  NOTE: the index leg of the test (move >8% while index <2%) is BLOCKED — index_ohlcv_1d has 51 rows.")

    print("\n== R7-H: Newey-West t on the DAILY mean-R series (overlap-corrected) ==")
    by_day2: dict[Any, list[float]] = collections.defaultdict(list)
    for t in trades:
        by_day2[t["entry"]].append(t["Rw"])
    for label, sub in (("ALL", trades), ("BUY", [t for t in trades if t["dir"] == "BUY"])):
        bd2: dict[Any, list[float]] = collections.defaultdict(list)
        for t in sub:
            bd2[t["entry"]].append(t["Rw"])
        ser = [statistics.mean(bd2[d]) for d in sorted(bd2)]
        if len(ser) > 20:
            nw = newey_west_t(ser, lag=SWING_DAYS - 1)
            n3, m3, sd3, se3, _, _ = moments(ser)
            print(f"  {label:<5} daily obs {n3:>4}  mean {m3:+.4f}  naive t {m3/se3 if se3 else float('nan'):+.2f}  "
                  f"Newey-West t(lag={SWING_DAYS-1}) {nw if nw is not None else float('nan'):+.2f}")

    print("\n== R7-J: Gemini's multivariate stop-width regression — geometry, or an ATR proxy? ==")
    for lbl, sub in (("ALL", trades), ("BUY only", [t for t in trades if t["dir"] == "BUY"])):
        if len(sub) < 30:
            continue
        cl = [t["entry"] for t in sub]
        print(f"  --- {lbl}: Rw ~ stop_width% (univariate)")
        ols_multi([t["Rw"] for t in sub], [[t["w"] for t in sub]], ["stop_width_pct"], cl)
        print(f"  --- {lbl}: Rw ~ stop_width% + ATR% + RVOL + log(close)  [Gemini's spec]")
        ols_multi([t["Rw"] for t in sub],
                  [[t["w"] for t in sub], [t["atr_pct"] for t in sub],
                   [t["rvol"] for t in sub], [t["log_close"] for t in sub]],
                  ["stop_width_pct", "atr_20_pct", "rvol_20", "log_close"], cl)
        print(f"  --- {lbl}: raw return % ~ same  (the economically relevant unit, no R denominator)")
        ols_multi([t["ret_pct"] for t in sub],
                  [[t["w"] for t in sub], [t["atr_pct"] for t in sub],
                   [t["rvol"] for t in sub], [t["log_close"] for t in sub]],
                  ["stop_width_pct", "atr_20_pct", "rvol_20", "log_close"], cl)
        print(f"  --- {lbl}: return/ATR20 ~ same  (the third unit)")
        ols_multi([t["ret_atr"] for t in sub],
                  [[t["w"] for t in sub], [t["atr_pct"] for t in sub],
                   [t["rvol"] for t in sub], [t["log_close"] for t in sub]],
                  ["stop_width_pct", "atr_20_pct", "rvol_20", "log_close"], cl)
    print("  (note: stop_width and ATR% are both volatility-loaded, so read the SEs, not just the betas)")
    wv = [t["w"] for t in trades]; av = [t["atr_pct"] for t in trades if t["atr_pct"] == t["atr_pct"]]
    if len(av) > 10:
        pw = [t["w"] for t in trades if t["atr_pct"] == t["atr_pct"]]
        print(f"  corr(stop_width%, ATR%) = {spearman(pw, av):+.4f}  (spearman, n={len(av)})")

    # =============================== ROUND 8 ===============================
    print("\n" + "=" * 78)
    print("ROUND 8 - settling the external audit's four recomputations")
    print("=" * 78)

    print("\n== R8-C1: MDE at 80% POWER beside the t=2 critical effect (2*SE is 50% power) ==")
    z80 = 2.8015951
    for lbl, sub, infl in (("mixed, all windows", trades, 1.00),
                           ("BUY, all windows", [t for t in trades if t["dir"] == "BUY"], 1.21)):
        if len(sub) < 10:
            continue
        v = [t["Rw"] for t in sub]
        sd = statistics.stdev(v)
        se = sd / math.sqrt(len(v)) * math.sqrt(infl)
        print(f"  {lbl:<22} n={len(v):>4} sigma {sd:.4f} infl {infl:.2f} SE {se:.4f}  "
              f"crit@t2 {2*se:+.4f}R   MDE@80% {z80*se:+.4f}R")

    print("\n== R8-C2: the two round-7 splits as INTERACTION tests, not subgroup levels ==")
    def interaction(label: str, a: list[float], b: list[float], na: str, nb: str) -> None:
        if len(a) < 3 or len(b) < 3:
            print(f"  {label:<26} (too few)"); return
        ma, mb = statistics.mean(a), statistics.mean(b)
        sea = statistics.stdev(a) / math.sqrt(len(a))
        seb = statistics.stdev(b) / math.sqrt(len(b))
        se = math.sqrt(sea**2 + seb**2)
        d = ma - mb
        print(f"  {label:<26} {na} {ma:+.4f} (n={len(a)}) vs {nb} {mb:+.4f} (n={len(b)})  "
              f"diff {d:+.4f}  SE {se:.4f}  t {d/se if se else float('nan'):+.2f}")
    interaction("direction (R7-A)", [t["Rw"] for t in trades if t["dir"] == "BUY"],
                [t["Rw"] for t in trades if t["dir"] == "SELL"], "BUY", "SELL")
    interaction("gap filter (R7-I)", [t["Rw"] for t in trades if not t.get("straddle")],
                [t["Rw"] for t in trades if t.get("straddle")], "clean", "straddling")
    print("  2x2 cells (mean R / n):")
    for d in ("BUY", "SELL"):
        for g, gl in ((False, "clean"), (True, "straddle")):
            v = [t["Rw"] for t in trades if t["dir"] == d and bool(t.get("straddle")) == g]
            if v:
                print(f"    {d:<5} {gl:<9} {statistics.mean(v):+.4f}  n={len(v)}")

    print("\n== R8-C4: the cost-in-R DISTRIBUTION - friction is 1/w, so E[cost] != cost(median w) ==")
    for bps in (25.5, 55.5):
        cin = [bps / 100.0 / t["w"] for t in trades if t["w"] > 0]
        wv = [t["w"] for t in trades if t["w"] > 0]
        med_w = statistics.median(wv)
        print(f"  round trip {bps:.1f} bps ({'explicit only' if bps < 30 else 'explicit + 15bps/leg slippage'}):")
        print(f"    cost at the MEDIAN stop ({med_w:.2f}%)          {bps/100.0/med_w:.4f}R   <- the scalar the document uses")
        print(f"    E[cost in R] across the book                {statistics.mean(cin):.4f}R   "
              f"=> understatement {statistics.mean(cin)/(bps/100.0/med_w):.2f}x")
        print(f"    median {statistics.median(cin):.4f}R  p90 {pctl(cin,.90):.4f}R  p99 {pctl(cin,.99):.4f}R  max {max(cin):.4f}R")
        reach = [bps / 100.0 / t["w"] for t in trades if t["w"] >= 2.0]
        if reach:
            print(f"    E[cost in R] on the live-reachable book (w>=2%)  {statistics.mean(reach):.4f}R  (n={len(reach)})")
        for lbl2, sub in (("ALL", trades), ("BUY", [t for t in trades if t["dir"] == "BUY"])):
            net = [t["Rw"] - bps / 100.0 / t["w"] for t in sub if t["w"] > 0]
            n2, m2, sd2, se2, _, _ = moments(net)
            print(f"    NET mean R, {lbl2:<4} (per-trade cost, not a scalar): {m2:+.4f}  SE {se2:.4f}  t {m2/se2 if se2 else float('nan'):+.2f}")

    print("\n== R8-C5: the MECHANICAL 1/w term - how much of a w-bucketed R gradient is arithmetic? ==")
    rng2 = random.Random(19)
    wv = [t["w"] for t in trades if t["w"] > 0]
    sd_ret = statistics.stdev([t["ret_pct"] for t in trades])
    print(f"  w drawn from the MEASURED swing distribution (n={len(wv)}), return INDEPENDENT of w, sd {sd_ret:.3f}%")
    print(f"  {'E[raw ret]':>11} {'R(w<2%)':>10} {'R(w>=2%)':>10} {'ALL':>10}")
    for mu_ret in (-0.10, -0.05, 0.0, float(statistics.mean([t["ret_pct"] for t in trades]))):
        lo: list[float] = []
        hi: list[float] = []
        allr: list[float] = []
        for _ in range(40000):
            sim_w = rng2.choice(wv)
            sim_r = clamp_ratio_f(rng2.gauss(mu_ret, sd_ret) / sim_w, WINSOR_R)
            allr.append(sim_r)
            (lo if sim_w < 2.0 else hi).append(sim_r)
        print(f"  {mu_ret:>+11.3f} {statistics.mean(lo):>+10.4f} {statistics.mean(hi):>+10.4f} {statistics.mean(allr):>+10.4f}")
    obs_lo = [t["Rw"] for t in trades if t["w"] < 2.0]
    obs_hi = [t["Rw"] for t in trades if t["w"] >= 2.0]
    if obs_lo and obs_hi:
        print(f"  {'MEASURED':>11} {statistics.mean(obs_lo):>+10.4f} {statistics.mean(obs_hi):>+10.4f} "
              f"{statistics.mean([t['Rw'] for t in trades]):>+10.4f}   (n {len(obs_lo)} / {len(obs_hi)})")
        interaction("  w<2% vs w>=2% (interaction)", obs_lo, obs_hi, "tight", "wide")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=250)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--clean-only", action="store_true",
                    help="skip panels whose 300-bar window straddles the 922-day ohlcv_1d hole")
    ap.add_argument("--dump-trades", default=None,
                    help="write the per-trade table to this CSV path (round 9 / Kimi R4): one "
                         "expensive pass, then every cell/contrast is a cheap read off the file")
    args = ap.parse_args()
    asyncio.run(main(args.stocks, args.stride, args.clean_only, args.dump_trades))
