"""Does requiring NEXT-DAY price confirmation before entering beat entering at the open?

## The question

Every trading text in `docs/reading/security_analysis/` inserts a stage our pipeline does not
have: a separate ENTRY TRIGGER, evaluated on the session AFTER the setup is found, that the
market must satisfy before any order exists.

    Elder     Screen 3: "place a buy order at the high of the previous day or a tick higher ...
                         good for one day only"
    Weinstein "Buy 1,000 XYZ at 12 1/8 STOP - 12 3/8 LIMIT" (confirm, but refuse to chase)
    Brooks    "enter on a stop ... you are being carried into the trade by the market's
               momentum. This is the single most reliable entry approach"
    Livermore "Why not buy it now at $1.14?" - "Because I don't know yet that it is going up."

Our engine fills every minted signal at the next bar's OPEN, unconditionally. This measures what
that rule would have done to OUR signals. Findings + citations:
`docs/reading/security-analysis-folder-takeaways-2026-09-09.md`.

Read-only study. The FROZEN `app/backtest/engine.py` mints the signals (identical set across
every variant — a trigger cannot change whether a signal is minted, its stop or its target) and
is neither edited nor subclassed; this module re-walks the exit with its own copy of the frozen
semantics, asserted trade-for-trade against the frozen `_simulate_trade` on the baseline before
any result is reported.

Two effects, measured SEPARATELY, because conflating them is how the R:R>=1 gate was promoted
and then refuted (2026-09-03):
  SELECTION  - trades that never confirm are never taken (a different trade SET).
  FILL COST  - a confirmed trade is entered HIGHER on the same SL/TP levels.

R = pnl_pct / risk_pct with risk_pct = |fill - SL| / fill * 100 - the risk ACTUALLY taken.
Risk-first sizing means a worse fill buys a SMALLER position; measuring in rupees at constant
qty would test bet size instead of entry timing (the error that inverted the first pass of the
horizon/stop-width study, 2026-08-25).

Corpus: the CA-clean window only. `ohlcv_1d` is CA-UNADJUSTED and a split gap would manufacture
BOTH a fake upside trigger and a fake stop.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time as _time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine, TradeRecord  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_CLEAN_SINCE = datetime(2023, 7, 3, tzinfo=UTC)
_TICK = 0.05

_COHORTS: list[tuple[str, float, float]] = [
    ("tight <2%", 0.0, 2.0),
    ("mid 2-5%", 2.0, 5.0),
    ("wide >5%", 5.0, 1e9),
]


@dataclass(frozen=True)
class Fill:
    idx: int
    price: float
    day_offset: int


@dataclass
class Row:
    classification: str
    direction: str
    planned_risk_pct: float
    actual_risk_pct: float
    pnl_pct: float
    hit_target: bool
    hit_sl: bool
    day_offset: int
    right_edge: bool

    @property
    def r(self) -> float:
        return self.pnl_pct / self.actual_risk_pct


async def _load_frames(
    universe: str, min_rows: int, max_stocks: int | None
) -> dict[str, pd.DataFrame]:
    where = "AND s.is_nifty50" if universe == "nifty50" else ""
    async with AsyncSessionFactory() as db:
        pick = await db.execute(
            text(
                f"SELECT s.symbol, COUNT(*) n, "
                f"       percentile_cont(0.5) WITHIN GROUP (ORDER BY o.close*o.volume) mdv "
                f"FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                f"WHERE s.is_active {where} AND o.time >= :since "
                f"GROUP BY s.symbol HAVING COUNT(*) >= :min_rows "
                f"ORDER BY mdv DESC"
            ),
            {"since": _CLEAN_SINCE, "min_rows": min_rows},
        )
        picked = pick.fetchall()
        if universe == "liquid":
            picked = [p for p in picked if p.mdv is not None and float(p.mdv) >= 5e7]
        if max_stocks is not None:
            picked = picked[:max_stocks]
        symbols = [p.symbol for p in picked]
        if not symbols:
            return {}
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume "
                    "FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                    "WHERE s.symbol = ANY(:syms) AND o.time >= :since "
                    "ORDER BY s.symbol, o.time"
                ),
                {"syms": symbols, "since": _CLEAN_SINCE},
            )
        ).fetchall()

    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for r in rows:
        by_symbol[r.symbol].append(r)
    frames: dict[str, pd.DataFrame] = {}
    for sym, rs in by_symbol.items():
        frames[sym] = pd.DataFrame(
            {
                "time": [r.time for r in rs],
                "open": [float(r.open) for r in rs],
                "high": [float(r.high) for r in rs],
                "low": [float(r.low) for r in rs],
                "close": [float(r.close) for r in rs],
                "volume": [int(r.volume) for r in rs],
            }
        ).set_index("time")
    return frames


def _walk_exit(
    candles: pd.DataFrame,
    fill_idx: int,
    direction: str,
    stop_loss: float,
    take_profit: float,
) -> tuple[int, float, bool, bool, bool]:
    """Frozen honest-fill exit walk, with the entry decoupled from the open.

    Replicated rather than called, because the frozen `_simulate_trade` hardcodes
    `entry = open[N+1]`. The semantics are copied exactly and asserted against the original
    in `_verify_walker`:
      * the fill bar itself is checked intrabar, but NOT for gaps (the entry IS inside it);
      * from the bar after the fill, a gap THROUGH a level exits at that bar's OPEN;
      * SL is checked before TP on both-hit bars;
      * a trade that reaches the right edge without touching either level is marked to the
        LAST CLOSE with both flags False -- the frozen engine's "signal expired" fallback.
        That last case is flagged so it can be excluded as a robustness check: it is a
        mark, not an outcome, and a confirmation rule enters LATER and is therefore more
        exposed to it.
    Returns (exit_idx, exit_price, hit_sl, hit_target, right_edge_mark).
    """
    buy = direction == "BUY"
    for i in range(fill_idx, len(candles)):
        c = candles.iloc[i]
        o, high, low = float(c["open"]), float(c["high"]), float(c["low"])
        if i > fill_idx:
            if (o <= stop_loss) if buy else (o >= stop_loss):
                return i, o, True, False, False
            if (o >= take_profit) if buy else (o <= take_profit):
                return i, o, False, True, False
        if (low <= stop_loss) if buy else (high >= stop_loss):
            return i, stop_loss, True, False, False
        if (high >= take_profit) if buy else (low <= take_profit):
            return i, take_profit, False, True, False
    last = len(candles) - 1
    return last, float(candles.iloc[last]["close"]), False, False, True


def _row_from(
    t: TradeRecord, candles: pd.DataFrame, fill: Fill, planned_entry: float
) -> Row | None:
    planned_risk = abs(planned_entry - t.stop_loss) / planned_entry * 100.0
    actual_risk = abs(fill.price - t.stop_loss) / fill.price * 100.0
    if planned_risk <= 0 or actual_risk <= 0:
        return None
    _, exit_price, hit_sl, hit_tp, right_edge = _walk_exit(
        candles, fill.idx, t.direction, t.stop_loss, t.take_profit
    )
    sign = 1 if t.direction == "BUY" else -1
    pnl_pct = sign * (exit_price - fill.price) / fill.price * 100.0
    return Row(
        classification=t.classification,
        direction=t.direction,
        planned_risk_pct=planned_risk,
        actual_risk_pct=actual_risk,
        pnl_pct=pnl_pct,
        hit_target=hit_tp,
        hit_sl=hit_sl,
        day_offset=fill.day_offset,
        right_edge=right_edge,
    )


def _confirm_fill(
    candles: pd.DataFrame,
    sidx: int,
    direction: str,
    stop_loss: float,
    window: int,
    cap_r: float | None,
    invalidate_on_sl: bool,
) -> Fill | None:
    """Stop entry one tick beyond the SIGNAL bar's extreme, live for `window` bars."""
    buy = direction == "BUY"
    sig = candles.iloc[sidx]
    trigger = float(sig["high"]) + _TICK if buy else float(sig["low"]) - _TICK
    risk_at_trigger = abs(trigger - stop_loss)
    if risk_at_trigger <= 0:
        return None
    ceiling = None
    if cap_r is not None:
        ceiling = trigger + cap_r * risk_at_trigger if buy else trigger - cap_r * risk_at_trigger

    for j in range(sidx + 1, min(sidx + 1 + window, len(candles))):
        c = candles.iloc[j]
        o, high, low = float(c["open"]), float(c["high"]), float(c["low"])
        reached = (high >= trigger) if buy else (low <= trigger)
        breached = (low <= stop_loss) if buy else (high >= stop_loss)
        if invalidate_on_sl and breached:
            return None
        if reached:
            price = max(o, trigger) if buy else min(o, trigger)
            if ceiling is not None and ((price > ceiling) if buy else (price < ceiling)):
                return None
            return Fill(idx=j, price=price, day_offset=j - sidx)
    return None


def _mean_t(xs: list[float]) -> tuple[float, float, float, int]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0, 0
    mean, med = statistics.mean(xs), statistics.median(xs)
    if n < 2:
        return mean, med, 0.0, n
    sd = statistics.stdev(xs)
    return mean, med, (mean / (sd / n**0.5) if sd > 0 else 0.0), n


def _cohort(risk_pct: float) -> str:
    for name, lo, hi in _COHORTS:
        if lo <= risk_pct < hi:
            return name
    return "?"


def _fmt_set(name: str, rows: list[Row], baseline_n: int) -> str:
    if not rows:
        return f"| {name} | 0 | - | - | - | - | - | - | - |"
    rs = [r.r for r in rows]
    mean, med, t, n = _mean_t(rs)
    win = sum(1 for r in rows if r.pnl_pct > 0) / n * 100
    tp = sum(1 for r in rows if r.hit_target) / n * 100
    kept = n / baseline_n * 100 if baseline_n else 0.0
    return (
        f"| {name} | {n} | {kept:.0f}% | {mean:+.3f} | {med:+.3f} | "
        f"{sum(rs):+.1f} | {win:.0f}% | {tp:.0f}% | {t:+.2f} |"
    )


def _verify_walker(engine: BacktestEngine, frames: dict[str, pd.DataFrame], limit: int) -> int:
    checked = 0
    for stock, candles in frames.items():
        pos = {ts: i for i, ts in enumerate(candles.index)}
        for t in engine.run_single_stock(stock, candles):
            fill_idx = pos[t.entry_date]
            ei, ep, sl, tp, _re = _walk_exit(
                candles, fill_idx, t.direction, t.stop_loss, t.take_profit
            )
            assert t.exit_price is not None, f"{stock} {t.entry_date}: frozen left it open"
            assert pd.Timestamp(candles.index[ei]) == t.exit_date, (
                f"{stock} {t.entry_date}: exit_date {candles.index[ei]} != {t.exit_date}"
            )
            assert abs(ep - t.exit_price) < 1e-9, (
                f"{stock} {t.entry_date}: exit_price {ep} != {t.exit_price}"
            )
            assert (sl, tp) == (t.hit_sl, t.hit_target), f"{stock} {t.entry_date}: flags"
            checked += 1
            if checked >= limit:
                return checked
    return checked


def _collect(  # noqa: C901 - one pass per stock: mint, classify the gap, then every variant
    frames: dict[str, pd.DataFrame], windows: list[int], cap_r: float
) -> tuple[dict[str, dict[tuple[str, Any], Row]], Counter[str], list[tuple[str, float, bool]]]:
    engine = BacktestEngine(BacktestConfig())
    names = ["baseline_open"]
    for w in windows:
        names += [f"stop_w{w}", f"stop_cap_w{w}", f"stop_cap_sl_w{w}"]
    variants: dict[str, dict[tuple[str, Any], Row]] = {n: {} for n in names}
    gap_census: Counter[str] = Counter()
    gap_rows: list[tuple[str, float, bool]] = []
    wmax = max(windows)

    done = 0
    total = len(frames)
    t0 = _time.time()
    for stock, candles in frames.items():
        done += 1
        if done % 5 == 0 or done == total:
            el = _time.time() - t0
            eta = el / done * (total - done)
            print(
                f"  [{done}/{total}] {stock} "
                f"{len(variants['baseline_open'])} trades  el={el / 60:.1f}m eta={eta / 60:.1f}m",
                file=sys.stderr,
                flush=True,
            )
        pos = {ts: i for i, ts in enumerate(candles.index)}
        for t in engine.run_single_stock(stock, candles):
            fidx = pos[t.entry_date]
            sidx = fidx - 1
            key = (stock, candles.index[sidx])
            base = _row_from(
                t, candles, Fill(idx=fidx, price=t.entry_price, day_offset=1), t.entry_price
            )
            if base is None:
                continue
            variants["baseline_open"][key] = base

            sig = candles.iloc[sidx]
            buy = t.direction == "BUY"
            s_close, s_high, s_low = float(sig["close"]), float(sig["high"]), float(sig["low"])
            o = t.entry_price
            if buy:
                gap = (
                    "full gap up" if o > s_high else ("partial up" if o > s_close else "no gap up")
                )
            else:
                gap = "full gap dn" if o < s_low else ("partial dn" if o < s_close else "no gap dn")
            gap_census[f"{t.direction} {gap}"] += 1

            confirmed_any = False
            for w in windows:
                for label, cap, inval in (
                    (f"stop_w{w}", None, False),
                    (f"stop_cap_w{w}", cap_r, False),
                    (f"stop_cap_sl_w{w}", cap_r, True),
                ):
                    fill = _confirm_fill(candles, sidx, t.direction, t.stop_loss, w, cap, inval)
                    if fill is None:
                        continue
                    row = _row_from(t, candles, fill, t.entry_price)
                    if row is not None:
                        variants[label][key] = row
                        if label == f"stop_w{wmax}":
                            confirmed_any = True
            gap_rows.append((f"{t.direction} {gap}", base.r, confirmed_any))
    return variants, gap_census, gap_rows


def _report(  # noqa: C901 - a linear report builder; splitting it would only scatter it
    variants: dict[str, dict[tuple[str, Any], Row]],
    gap_census: Counter[str],
    gap_rows: list[tuple[str, float, bool]],
    windows: list[int],
    cap_r: float,
    universe: str,
    n_stocks: int,
    verified: int,
) -> str:
    base = variants["baseline_open"]
    bn = len(base)
    out: list[str] = []
    a = out.append
    a("# Entry-confirmation study - does the market have to prove it first?\n")
    a(
        f"_Generated {datetime.now(tz=UTC).date()} - universe `{universe}` - {n_stocks} stocks - "
        f"CA-clean window from {_CLEAN_SINCE.date()} - {bn} resolved baseline trades._\n"
    )
    a(
        f"\nWalker verified against the frozen `_simulate_trade` on **{verified}** trades "
        f"(exit date, exit price and both flags identical). Read-only; the frozen engine was "
        f"neither edited nor subclassed.\n"
    )

    a("\n## 1. What the whole book looks like under each entry rule\n")
    a(
        "`kept` = share of the baseline's trades this rule still takes. R is measured against "
        "the risk ACTUALLY taken (`|fill - SL|`), so a worse fill is already charged for. "
        "`tp_hit` is a target touch; `win` also counts a right-edge mark that happens to be "
        "positive. They diverge only by those marks - see the robustness table.\n"
    )
    a("\n| entry rule | n | kept | mean R | median R | total R | win | tp_hit | t |")
    a("|---|---|---|---|---|---|---|---|---|")
    a(_fmt_set("baseline: fill at next open (frozen)", list(base.values()), bn))
    for w in windows:
        a(_fmt_set(f"stop @ prior-bar extreme, {w}d", list(variants[f"stop_w{w}"].values()), bn))
        a(
            _fmt_set(
                f"... + {cap_r:.2f}R ceiling (stop-limit), {w}d",
                list(variants[f"stop_cap_w{w}"].values()),
                bn,
            )
        )
        a(
            _fmt_set(
                f"... + dead if stop hit first, {w}d",
                list(variants[f"stop_cap_sl_w{w}"].values()),
                bn,
            )
        )

    a("\n### 1b. Robustness: resolved trades only (right-edge marks dropped)\n")
    a(
        "A trade still open at the right edge is marked to the last close by the frozen "
        "engine - a mark, not an outcome. A confirmation rule enters LATER, so it is more "
        "exposed to that fudge; if the ranking only survives WITH the marks, it is an "
        "artifact of the corpus end, not an entry effect.\n"
    )
    a("\n| entry rule | n | mean R | median R | total R | tp_hit | t |")
    a("|---|---|---|---|---|---|---|")

    def _resolved(rows: list[Row], label: str) -> str:
        rr = [r for r in rows if not r.right_edge]
        if not rr:
            return f"| {label} | 0 | - | - | - | - | - |"
        xs = [r.r for r in rr]
        mean, med, t, n = _mean_t(xs)
        tp = sum(1 for r in rr if r.hit_target) / n * 100
        return (
            f"| {label} | {n} | {mean:+.3f} | {med:+.3f} | {sum(xs):+.1f} | {tp:.0f}% | {t:+.2f} |"
        )

    a(_resolved(list(base.values()), "baseline: fill at next open (frozen)"))
    for w in windows:
        a(_resolved(list(variants[f"stop_cap_sl_w{w}"].values()), f"stop+cap+sl, {w}d"))
    n_marks = sum(1 for r in base.values() if r.right_edge)
    a(f"\n_Right-edge marks in the baseline: {n_marks} of {bn} ({n_marks / bn * 100:.1f}%)._\n")

    a("\n## 2. Selection vs fill cost - the two effects separated\n")
    a(
        "Left block = the baseline restricted to the trades this rule also took (pure "
        "selection). Right = paired mean dR on that same intersection (pure fill cost).\n"
    )
    a("\n| entry rule | n_int | baseline R on int | variant R on int | paired dR | t(dR) |")
    a("|---|---|---|---|---|---|")
    for w in windows:
        for label, pretty in (
            (f"stop_w{w}", f"stop, {w}d"),
            (f"stop_cap_w{w}", f"stop+cap, {w}d"),
            (f"stop_cap_sl_w{w}", f"stop+cap+sl, {w}d"),
        ):
            keys = set(variants[label]) & set(base)
            if not keys:
                a(f"| {pretty} | 0 | - | - | - | - |")
                continue
            b = [base[k].r for k in keys]
            v = [variants[label][k].r for k in keys]
            d = [variants[label][k].r - base[k].r for k in keys]
            dm, _, dt, _ = _mean_t(d)
            a(
                f"| {pretty} | {len(keys)} | {statistics.mean(b):+.3f} | "
                f"{statistics.mean(v):+.3f} | {dm:+.3f} | {dt:+.2f} |"
            )

    a("\n## 3. Does it survive inside every stop-width cohort?\n")
    a(
        "The mandatory check: the R:R>=1 gate looked good in aggregate because it re-sorted the "
        "stop-width mix. A rule that only wins by shifting the mix is the same trap.\n"
    )
    w_focus = windows[-1]
    a(f"\n| cohort | baseline n / mean R | stop+cap+sl {w_focus}d n / mean R | delta |")
    a("|---|---|---|---|")
    for cname, _, _ in _COHORTS:
        bb = [r.r for r in base.values() if _cohort(r.planned_risk_pct) == cname]
        vv = [
            r.r
            for r in variants[f"stop_cap_sl_w{w_focus}"].values()
            if _cohort(r.planned_risk_pct) == cname
        ]
        bm = statistics.mean(bb) if bb else 0.0
        vm = statistics.mean(vv) if vv else 0.0
        a(f"| {cname} | {len(bb)} / {bm:+.3f} | {len(vv)} / {vm:+.3f} | {vm - bm:+.3f} |")

    a("\n## 3b. By classification\n")
    a(f"\n| class | baseline n / mean R | stop+cap+sl {w_focus}d n / mean R | delta |")
    a("|---|---|---|---|")
    classes = sorted({r.classification for r in base.values()})
    for cl in classes:
        bb = [r.r for r in base.values() if r.classification == cl]
        vv = [r.r for r in variants[f"stop_cap_sl_w{w_focus}"].values() if r.classification == cl]
        bm = statistics.mean(bb) if bb else 0.0
        vm = statistics.mean(vv) if vv else 0.0
        a(f"| {cl} | {len(bb)} / {bm:+.3f} | {len(vv)} / {vm:+.3f} | {vm - bm:+.3f} |")

    a("\n## 3c. By direction\n")
    a(f"\n| side | baseline n / mean R | stop+cap+sl {w_focus}d n / mean R | delta |")
    a("|---|---|---|---|")
    for side in ("BUY", "SELL"):
        bb = [r.r for r in base.values() if r.direction == side]
        vv = [r.r for r in variants[f"stop_cap_sl_w{w_focus}"].values() if r.direction == side]
        bm = statistics.mean(bb) if bb else 0.0
        vm = statistics.mean(vv) if vv else 0.0
        a(f"| {side} | {len(bb)} / {bm:+.3f} | {len(vv)} / {vm:+.3f} | {vm - bm:+.3f} |")

    a("\n## 4. When does confirmation arrive? (the alert-timing question)\n")
    a(
        "Day 1 = the bar the frozen engine fills on. This is the distribution the alert clock "
        "has to cover: a 1-day window is a different product from a 5-day one.\n"
    )
    wmax = max(windows)
    day = Counter(r.day_offset for r in variants[f"stop_w{wmax}"].values())
    a(f"\n| day | triggered | cumulative share of {bn} baseline trades |")
    a("|---|---|---|")
    cum = 0
    for offset in sorted(day):
        cum += day[offset]
        a(f"| +{offset} | {day[offset]} | {cum / bn * 100:.0f}% |")
    a(f"| never (within {wmax}d) | {bn - cum} | - |")

    a("\n## 5. What the OPEN alone tells you (the gap census)\n")
    a(
        "Where the fill bar opened relative to the signal bar, and how the frozen baseline then "
        "did. `confirmed` = the trade also cleared the prior-bar extreme within the window.\n"
    )
    by_gap: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for g, r, c in gap_rows:
        by_gap[g].append((r, c))
    a("\n| open vs signal bar | n | mean baseline R | share confirmed |")
    a("|---|---|---|---|")
    for g in sorted(by_gap, key=lambda k: -len(by_gap[k])):
        rs = [x[0] for x in by_gap[g]]
        cf = sum(1 for x in by_gap[g] if x[1]) / len(by_gap[g]) * 100
        a(f"| {g} | {len(rs)} | {statistics.mean(rs):+.3f} | {cf:.0f}% |")
    a(f"\n_Census check: {sum(gap_census.values())} classified._\n")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", choices=["nifty50", "liquid", "all"], default="liquid")
    ap.add_argument("--max-stocks", type=int, default=250)
    ap.add_argument("--min-rows", type=int, default=200)
    ap.add_argument("--windows", default="1,2,3,5")
    ap.add_argument("--cap-r", type=float, default=0.33)
    ap.add_argument("--verify-walker", type=int, default=400)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    windows = sorted({int(x) for x in args.windows.split(",") if x.strip()})
    frames = asyncio.run(_load_frames(args.universe, args.min_rows, args.max_stocks))
    if not frames:
        print("no stocks matched")
        return
    print(f"loaded {len(frames)} stocks", file=sys.stderr)

    verified = 0
    if args.verify_walker:
        engine = BacktestEngine(BacktestConfig())
        verified = _verify_walker(engine, frames, args.verify_walker)
        print(f"walker verified on {verified} frozen trades", file=sys.stderr)

    variants, census, gap_rows = _collect(frames, windows, args.cap_r)
    md = _report(
        variants, census, gap_rows, windows, args.cap_r, args.universe, len(frames), verified
    )
    out = (
        Path(args.out)
        if args.out
        else _OUT_DIR / f"entry-confirmation-study-{datetime.now(tz=UTC).date()}.md"
    )
    out.write_text(md)
    print(md)
    print(f"\nwritten to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
