"""Read-only probe: what IS a positional signal, and what does it do?

The daily engine emits `positional` on the 1d timeframe **only** when the
MULTIBAGGER_EMA bonus factor scores (`classifier.classify_signal`), so the
positional class is not a horizon choice — it is one factor's footprint. That
makes positional rare (the general selectivity probe caught 13 of 4,511 panels),
and nothing measured so far describes it on its own terms.

This probe answers, for the positional class specifically:

  1. **Population** — how often does the multibagger condition hold, how often
     does the resulting panel clear the >=70% gate, and which factors are
     actually scoring underneath it (the signal HEADLINE only shows the top 3 by
     |score|, so it cannot answer this).
  2. **Geometry** — the positional stop is `EMA20` with **no class cap**
     (`risk.compute_levels` skips the cap check for positional) and the target is
     a flat +/-15%. What stop width, R:R and notional does that actually produce?
  3. **The three-way rule split** — `signal_service` passes `ema20_daily`,
     `profiles/pipeline.py` does NOT, and `backtest/engine.py` does not either.
     The same signal therefore gets a stop at EMA20 on one path and a flat 5% on
     the other two. This measures both rules on the same panels.
  4. **Outcome** — forward R through the FROZEN walker
     (`BacktestEngine._simulate_trade`, imported and called, never reimplemented),
     both unbounded (frozen default) and capped at the 30-trading-day positional
     validity via the sanctioned `session_last` freeze-extension.

Conventions enforced (docs/SYSTEM_REVIEW_FOR_QUANT.md 11.4):
  - corporate actions: `ohlcv_1d` is CA-UNADJUSTED, so any holding span with a
    close-to-close move > 25% is DROPPED and the count printed;
  - R is winsorized at `app.core.ratios.WINSOR_R` wherever it is averaged, and
    the median is printed beside the mean;
  - the trade series goes through `moving_block_bootstrap` — a plain t on
    overlapping trades is optimistic.

SELECT-only. The frozen engine is imported and called exactly as the nightly job
calls it; nothing under app/analysis/ or app/backtest/ is edited or subclassed.

Run:  cd backend && uv run python scripts/positional_probe.py
      [--stocks 250] [--swing-stride 25]
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import math
import statistics
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analysis.confluence import run_all_factors, score_from_factors
from app.analysis.indicators.ema import _ema, multibagger_ema_factor
from app.analysis.risk import compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import swing_levels
from app.backtest.engine import BacktestConfig, BacktestEngine
from app.core.ratios import WINSOR_R, clamp_ratio_f
from app.db.session import AsyncSessionFactory
from app.services.block_bootstrap import moving_block_bootstrap, render_lines
from app.signals.classifier import classify_signal
from app.signals.entry_quality import factor_diversity
from app.signals.risk_guards import safe_levels
from app.services.market_calendar import observed_session_index, window_has_holes

# ⭐ B5 / W2: the basket, its matched-window helper and the ATR are DEFINED ONCE in the swing
# probe and imported here. Re-deriving an "equal-weight universe return" in a second file is
# exactly how two numbers that must agree stop agreeing — and §16.1c's time-dimension rule
# exists because a benchmark measured on one sample was subtracted from another.
from swing_dependence_probe import (  # noqa: E402
    _as_date,
    atr20,
    basket_series,
    basket_window,
)

WINDOW = 300
CAPITAL = Decimal("100000")
RISK_PCT = Decimal("2.0")
CA_JUMP = 0.25          # |close-to-close| above this = an unadjusted corporate action
POSITIONAL_DAYS = 30    # SIGNAL_ENGINE.md 5 validity, in trading days
SWING_DAYS = 5


def q(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))] if xs else float("nan")


async def load_frames(n_stocks: int) -> dict[str, pd.DataFrame]:
    async with AsyncSessionFactory() as db:
        ids = [
            r[0]
            for r in (
                await db.execute(
                    text(
                        """
                        SELECT stock_id FROM ohlcv_1d
                        WHERE time > now() - interval '180 days'
                        GROUP BY stock_id HAVING count(*) > 100
                        ORDER BY percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY close * volume) DESC
                        LIMIT :n
                        """
                    ),
                    {"n": n_stocks},
                )
            ).all()
        ]
        rows = (
            await db.execute(
                text(
                    """
                    SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume
                    FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id
                    WHERE o.stock_id = ANY(:i) AND o.is_complete
                    ORDER BY s.symbol, o.time
                    """
                ),
                {"i": ids},
            )
        ).all()
    grouped: dict[str, list[Any]] = collections.defaultdict(list)
    for r in rows:
        grouped[r[0]].append(r)
    frames: dict[str, pd.DataFrame] = {}
    for sym, rs in grouped.items():
        if len(rs) < WINDOW + 40:
            continue
        frames[sym] = pd.DataFrame(
            {
                "open": [float(r[2]) for r in rs],
                "high": [float(r[3]) for r in rs],
                "low": [float(r[4]) for r in rs],
                "close": [float(r[5]) for r in rs],
                "volume": [float(r[6]) for r in rs],
            },
            index=pd.DatetimeIndex([r[1] for r in rs]),
        )
    return frames


def breakout_candidates(df: pd.DataFrame) -> list[int]:
    """Bars satisfying the multibagger BREAKOUT half, vectorized and exact.

    `multibagger_ema_factor` needs a green candle whose body is >= 1.5x the mean
    body of the last 20 bars. That half depends only on the last 20 bars, so it is
    window-independent and can be screened first; the EMA20-vs-EMA200 half must be
    evaluated on the 300-bar window and is checked per candidate.
    """
    body = (df["close"] - df["open"]).abs()
    avg = body.rolling(20).mean()
    green = df["close"] > df["open"]
    ok = green & (body >= 1.5 * avg)
    return [i for i, v in enumerate(ok.to_numpy()) if v and WINDOW - 1 <= i < len(df) - 1]


def r_from(record: Any, stop: float) -> float | None:
    """Realised R against the risk carried AT THE FILL (entry is the next open)."""
    risk_pct = abs(record.entry_price - stop) / record.entry_price * 100
    if risk_pct <= 0 or record.pnl_pct is None:
        return None
    return float(record.pnl_pct) / float(risk_pct)


def ca_clean(df: pd.DataFrame, lo: int, hi: int) -> bool:
    seg = df["close"].iloc[max(0, lo - 1) : hi + 1]
    if len(seg) < 2:
        return True
    return bool((seg.pct_change().abs().dropna() <= CA_JUMP).all())


def summarize(rs: list[float], label: str) -> None:
    if not rs:
        print(f"  {label:<34} (none)")
        return
    w = [clamp_ratio_f(x, WINSOR_R) for x in rs]
    wins = sum(1 for x in rs if x > 0)
    print(
        f"  {label:<34} n={len(rs):>4}  meanR {statistics.mean(w):+.3f}  "
        f"medR {statistics.median(rs):+.3f}  win {100 * wins / len(rs):4.1f}%  "
        f"totR {sum(w):+8.1f}"
    )


async def main(n_stocks: int, swing_stride: int, dump: str | None = None) -> None:  # noqa: C901 — one linear measurement pass
    frames = await load_frames(n_stocks)
    print(f"stocks with usable history: {len(frames)}")
    engine = BacktestEngine(BacktestConfig(capital=CAPITAL, risk_pct=RISK_PCT))

    # ── B5: the three columns E1 was re-specified to need (round 10, §12.26) ──────────
    # E1 as originally written asked for R, raw % and net ₹. Re-reporting in raw % removes
    # the `1/w` amplification and does NOT remove the SECOND mechanical term:
    # `R = (α + drift·T)/w`, and `T` rises with `w` at t = +6.69 while the universe drifted
    # +0.0816%/day. Only a benchmark PAIRED to each trade's own window removes it — measured
    # on the swing book the tight-vs-wide contrast decays −0.386 (R) → −0.262 (raw %) →
    # **+0.069 (excess vs basket)** and flips sign.
    async with AsyncSessionFactory() as _db:
        sessions = await observed_session_index(_db)
    bser = basket_series(frames)
    print(f"observed market sessions: {len(sessions):,}   basket sessions: {len(bser):,}")
    trades: list[dict[str, Any]] = []

    mb_bars = gate_pass = 0
    part: collections.Counter[str] = collections.Counter()
    dirs: collections.Counter[str] = collections.Counter()
    conf: list[float] = []
    n_scoring: list[float] = []
    ema_sl: list[float] = []
    ema_rr: list[float] = []
    ema_notional: list[float] = []
    ema_reject = flat_reject = 0
    ca_dropped = 0
    r_ema: list[float] = []
    r_flat: list[float] = []
    r_ema_cap: list[float] = []
    r_flat_cap: list[float] = []
    r_swing: list[float] = []
    swing_seen = swing_pass = 0
    tight: list[tuple[float, float]] = []   # (stop width %, R) on the EMA20 rule
    div_single = div_dominant = div_blocked = 0   # what the ONE active gate would do
    mb_share: list[float] = []              # multibagger's share of the confluence
    paired: list[tuple[float, float]] = []  # (R under EMA20, R under flat-5%) same panel
    paired_swing: list[tuple[float, float]] = []  # (R as positional, R if it were a swing)
    swing_rule_reject = 0                   # same panel, rejected by the 8% SWING cap
    through_stop = 0                        # fill already at/through the stop — see below

    for sym, df in frames.items():
        closes = df["close"]
        for i in breakout_candidates(df):
            window = df.iloc[i - WINDOW + 1 : i + 1]
            straddles = window_has_holes(
                sessions, window.index[0].date(), window.index[-1].date(), WINDOW
            )
            if multibagger_ema_factor(window).score <= 0:
                continue
            mb_bars += 1
            factors = run_all_factors(window, "1d")
            result = score_from_factors(factors, window, 70)
            if result is None:
                continue
            if classify_signal("1d", result.factors, result.is_multibagger) != "positional":
                continue
            gate_pass += 1
            scored = [f for f in factors if f.score != 0.0]
            n_scoring.append(len(scored))
            for f in scored:
                part[f.name] += 1
            dirs[result.direction] += 1
            conf.append(result.confidence_pct)

            # What the only ACTIVE order-path gate (entry_diversity) would do here.
            fs = {f.name: {"weight": f.weight, "score": f.score} for f in result.factors}
            count, dominant = factor_diversity(fs)
            # The two limbs OVERLAP: a single scoring factor is by definition 100%
            # of the confluence, so it trips both. Count the UNION for "blocked".
            single = bool(count) and count < 2
            dom = dominant is not None and float(dominant) > 0.90
            div_single += single
            div_dominant += dom
            div_blocked += single or dom
            total_contrib = sum(abs(f.weight * f.score) for f in result.factors)
            if total_contrib:
                mb_share.append(
                    100 * abs(next(f.weight * f.score for f in result.factors
                                   if f.name == "MULTIBAGGER_EMA")) / total_contrib
                )

            entry = Decimal(str(closes.iloc[i]))
            low, high = swing_levels(window)
            e20s = _ema(window["close"], 20)
            ema20 = Decimal(str(e20s.iloc[-1])) if not e20s.dropna().empty else None

            panel: dict[str, float] = {}
            for tag, ema_arg in (("ema", ema20), ("flat", None)):
                lv = safe_levels(result.direction, "positional", entry, low, high, ema_arg)
                if lv is None:
                    if tag == "ema":
                        ema_reject += 1
                    else:
                        flat_reject += 1
                    continue
                stop, target = lv
                width = float(abs(entry - stop) / entry * 100)
                qty = volatility_adjusted_qty(
                    compute_quantity(CAPITAL, RISK_PCT, entry, stop), window
                )
                if qty == 0:
                    continue
                if tag == "ema":
                    ema_sl.append(width)
                    ema_rr.append(float(abs(target - entry) / abs(entry - stop)))
                    ema_notional.append(float(entry) * qty)
                # ⚠ The frozen walker's gap check is skipped ON the fill bar, so a BUY
                # whose fill (open[i+1]) has already gapped BELOW its stop exits AT the
                # stop — a price ABOVE the entry — and is scored as roughly +1R when it
                # was in fact an immediate loss. The live path never opens such a
                # position: `paper_broker` has an unconditional through-stop rejection.
                # Exclude it here so the corpus measures what the system would trade.
                fill_open = float(df["open"].iloc[i + 1])
                through = (
                    fill_open <= float(stop) if result.direction == "BUY"
                    else fill_open >= float(stop)
                )
                if through:
                    if tag == "ema":
                        through_stop += 1
                    continue
                for capped in (False, True):
                    sl_flags = None
                    if capped:
                        sl_flags = [False] * len(df)
                        stop_bar = i + 1 + POSITIONAL_DAYS
                        if stop_bar >= len(df):
                            continue
                        sl_flags[stop_bar] = True
                    rec = engine._simulate_trade(  # noqa: SLF001 — frozen walker, called not copied
                        stock=sym, signal_candle_idx=i, direction=result.direction,
                        classification="positional", confidence_pct=result.confidence_pct,
                        stop_loss=float(stop), take_profit=float(target), qty=qty,
                        candles=df, session_last=sl_flags,
                    )
                    if rec is None or rec.exit_date is None:
                        continue
                    xi = int(df.index.get_loc(rec.exit_date))
                    if not ca_clean(df, i + 1, xi):
                        if tag == "ema" and not capped:
                            ca_dropped += 1
                        continue
                    rr = r_from(rec, float(stop))
                    if rr is None:
                        continue

                    # ── B5: one record per simulated trade, in FOUR units + T + the
                    # paired basket. `rule`/`capped` are carried rather than filtered so a
                    # downstream cut can choose its own cohort without a second walk.
                    # `r_from` already returned non-None, so `pnl_pct` is set — but say so
                    # explicitly rather than asserting it through a cast.
                    _pnl = rec.pnl_pct
                    if _pnl is None:
                        continue
                    _e_d, _x_d = df.index[i + 1].date(), _as_date(rec.exit_date)
                    _bench, _T = basket_window(bser, _e_d, _x_d)
                    _a = atr20(df, i)
                    _px = rec.entry_price
                    trades.append({
                        "sym": sym, "entry": _e_d, "exit": _x_d, "T": _T,
                        "rule": tag, "capped": capped, "dir": result.direction,
                        "w": width, "R": rr, "Rw": clamp_ratio_f(rr, WINSOR_R),
                        "ret_pct": float(_pnl), "bench": _bench,
                        "excess": float(_pnl) - _bench,
                        "ret_atr": (float(_pnl) / 100 * _px / _a)
                        if _a and _a == _a else float("nan"),
                        "cash": float(_pnl) / 100.0 * _px * qty,
                        "conf": result.confidence_pct, "straddle": straddles,
                        "atr_pct": (_a / _px * 100) if _a and _a == _a and _px else float("nan"),
                        "entry_px": _px, "qty": qty,
                    })

                    if tag == "ema" and not capped:
                        r_ema.append(rr)
                        tight.append((width, rr))
                        panel["ema"] = rr
                    elif tag == "ema":
                        r_ema_cap.append(rr)
                        panel["ema_cap"] = rr
                    elif not capped:
                        r_flat.append(rr)
                        panel["flat"] = rr
                    else:
                        r_flat_cap.append(rr)

            if "ema" in panel and "flat" in panel:
                paired.append((panel["ema"], panel["flat"]))

            # Counterfactual: what if this panel had NOT been relabelled positional?
            # Same signal, swing rule set — pivot stop, 8% cap, +6% target, 5-day validity.
            sw = safe_levels(result.direction, "swing", entry, low, high, None)
            if sw is None:
                swing_rule_reject += 1
            elif "ema_cap" in panel:
                s_stop, s_target = sw
                s_qty = volatility_adjusted_qty(
                    compute_quantity(CAPITAL, RISK_PCT, entry, s_stop), window
                )
                stop_bar = i + 1 + SWING_DAYS
                s_open = float(df["open"].iloc[i + 1])
                s_through = (
                    s_open <= float(s_stop) if result.direction == "BUY"
                    else s_open >= float(s_stop)
                )
                if s_qty and not s_through and stop_bar < len(df):
                    flags = [False] * len(df)
                    flags[stop_bar] = True
                    srec = engine._simulate_trade(  # noqa: SLF001
                        stock=sym, signal_candle_idx=i, direction=result.direction,
                        classification="swing", confidence_pct=result.confidence_pct,
                        stop_loss=float(s_stop), take_profit=float(s_target), qty=s_qty,
                        candles=df, session_last=flags,
                    )
                    if srec is not None and srec.exit_date is not None:
                        sxi = int(df.index.get_loc(srec.exit_date))
                        if ca_clean(df, i + 1, sxi):
                            s_r = r_from(srec, float(s_stop))
                            if s_r is not None:
                                paired_swing.append((panel["ema_cap"], s_r))

        # matched SWING baseline on the same names, strided
        for i in range(WINDOW - 1, len(df) - 1, swing_stride) if swing_stride > 0 else []:
            window = df.iloc[i - WINDOW + 1 : i + 1]
            swing_seen += 1
            try:
                factors = run_all_factors(window, "1d")
            except Exception:  # noqa: BLE001 — a bad window must not stop the probe
                continue
            result = score_from_factors(factors, window, 70)
            if result is None:
                continue
            if classify_signal("1d", result.factors, result.is_multibagger) != "swing":
                continue
            entry = Decimal(str(closes.iloc[i]))
            low, high = swing_levels(window)
            lv = safe_levels(result.direction, "swing", entry, low, high, None)
            if lv is None:
                continue
            swing_pass += 1
            stop, target = lv
            qty = volatility_adjusted_qty(
                compute_quantity(CAPITAL, RISK_PCT, entry, stop), window
            )
            if qty == 0:
                continue
            rec = engine._simulate_trade(  # noqa: SLF001
                stock=sym, signal_candle_idx=i, direction=result.direction,
                classification="swing", confidence_pct=result.confidence_pct,
                stop_loss=float(stop), take_profit=float(target), qty=qty,
                candles=df, session_last=None,
            )
            if rec is None or rec.exit_date is None:
                continue
            xi = int(df.index.get_loc(rec.exit_date))
            if not ca_clean(df, i + 1, xi):
                continue
            rr = r_from(rec, float(stop))
            if rr is not None:
                r_swing.append(rr)

    print("\n== population ==")
    print(f"  bars meeting the full multibagger condition : {mb_bars:,}")
    print(f"  of those, clearing the >=70% gate           : {gate_pass:,} "
          f"({100 * gate_pass / mb_bars:.1f}%)" if mb_bars else "")
    print(f"  direction split                             : {dict(dirs)}")
    if conf:
        print(f"  confidence  p10 {q(conf, 0.1):.0f} · median {statistics.median(conf):.0f} "
              f"· p90 {q(conf, 0.9):.0f}")
        print(f"  scoring factors per signal  p10 {q(n_scoring, 0.1):.0f} · "
              f"median {statistics.median(n_scoring):.0f} · p90 {q(n_scoring, 0.9):.0f}")
    print("\n== which factors actually score on a POSITIONAL panel ==")
    for name, c in part.most_common():
        print(f"  {name:<20} {100 * c / gate_pass:5.1f}%")

    if gate_pass:
        blocked = div_blocked
        print("\n== the ONE active gate (entry_diversity) applied to positional ==")
        print(f"  < 2 scoring factors            : {div_single} "
              f"({100 * div_single / gate_pass:.1f}%)")
        print(f"  one factor > 90% of confluence : {div_dominant} "
              f"({100 * div_dominant / gate_pass:.1f}%)")
        print(f"  would be BLOCKED at order time : {blocked} "
              f"({100 * blocked / gate_pass:.1f}%)")
    if mb_share:
        print(f"  MULTIBAGGER_EMA share of the confluence: p10 {q(mb_share, 0.1):.0f}% · "
              f"median {statistics.median(mb_share):.0f}% · p90 {q(mb_share, 0.9):.0f}%")

    print("\n== level geometry, the two rules that both exist in the codebase ==")
    print(f"  EMA20 rule (signal_service): rejected wrong-side {ema_reject} "
          f"of {gate_pass} ({100 * ema_reject / gate_pass:.1f}%)" if gate_pass else "")
    print(f"  flat-5% rule (profiles + backtest): rejected {flat_reject}")
    if ema_sl:
        print(f"  EMA20 stop width %: p10 {q(ema_sl, 0.1):.2f} · median "
              f"{statistics.median(ema_sl):.2f} · p90 {q(ema_sl, 0.9):.2f} · max {max(ema_sl):.2f}")
        u2 = 100 * sum(1 for x in ema_sl if x < 2) / len(ema_sl)
        o8 = 100 * sum(1 for x in ema_sl if x > 8) / len(ema_sl)
        print(f"    under 2% of price: {u2:.1f}% · beyond the 8% SWING cap: {o8:.1f}%")
        print(f"  EMA20 R:R: p10 {q(ema_rr, 0.1):.2f} · median {statistics.median(ema_rr):.2f} "
              f"· p90 {q(ema_rr, 0.9):.2f} · below 1.0: "
              f"{100 * sum(1 for x in ema_rr if x < 1) / len(ema_rr):.1f}%")
        print("  flat-5% R:R is exactly 3.00 by construction (15% target / 5% stop)")
        over = 100 * sum(1 for x in ema_notional if x > float(CAPITAL)) / len(ema_notional)
        print(f"  notional at Rs1L/2%: median Rs{q(ema_notional, 0.5):,.0f} · "
              f"p90 Rs{q(ema_notional, 0.9):,.0f} · over the 1.0x cap: {over:.1f}%")

    print(f"\n  fills already AT/THROUGH the stop, excluded (the live broker rejects these; "
          f"the frozen walker mis-scores them as ~+1R): {through_stop}")
    print(f"\n== forward outcome (frozen walker; fill at next open; "
          f"{ca_dropped} trades dropped as unadjusted corporate actions) ==")
    summarize(r_ema, "positional, EMA20 stop, no horizon")
    summarize(r_ema_cap, f"positional, EMA20 stop, {POSITIONAL_DAYS}d cap")
    summarize(r_flat, "positional, flat-5% stop, no horizon")
    summarize(r_flat_cap, f"positional, flat-5% stop, {POSITIONAL_DAYS}d cap")
    summarize(r_swing, "swing baseline (same names)")

    for label, series in (("positional EMA20", r_ema), ("positional flat-5%", r_flat),
                          ("swing baseline", r_swing)):
        for line in render_lines(moving_block_bootstrap(series), label=label):
            print(line)

    if len(paired) > 2:
        d = [clamp_ratio_f(a, WINSOR_R) - clamp_ratio_f(b, WINSOR_R) for a, b in paired]
        mean_d = statistics.mean(d)
        sd = statistics.stdev(d)
        t = mean_d / (sd / (len(d) ** 0.5)) if sd else float("nan")
        print("\n== EMA20 vs flat-5% on the SAME panels (paired — the right instrument) ==")
        print(f"  n={len(d)}  mean dR {mean_d:+.3f}  median dR "
              f"{statistics.median(d):+.3f}  t={t:+.2f}")
        print("  (dR > 0 would mean the EMA20 stop beats the flat 5% stop on identical signals)")

    if len(paired_swing) > 2:
        d = [clamp_ratio_f(a, WINSOR_R) - clamp_ratio_f(b, WINSOR_R) for a, b in paired_swing]
        mean_d = statistics.mean(d)
        sd = statistics.stdev(d)
        t = mean_d / (sd / (len(d) ** 0.5)) if sd else float("nan")
        print("\n== should the class exist? SAME panels, positional rules vs swing rules ==")
        print(f"  rejected by the 8% swing cap that positional does not apply: "
              f"{swing_rule_reject} of {gate_pass} ({100 * swing_rule_reject / gate_pass:.1f}%)")
        summarize([a for a, _ in paired_swing], "as POSITIONAL (EMA20, 30d)")
        summarize([b for _, b in paired_swing], "as SWING (pivot stop, +6%, 5d)")
        print(f"  paired n={len(d)}  mean dR {mean_d:+.3f}  median dR "
              f"{statistics.median(d):+.3f}  t={t:+.2f}")
        print("  (dR > 0 would mean the positional relabelling BEATS leaving it a swing)")

    if tight:
        print("\n== does the stop width explain the outcome? (EMA20 rule) ==")
        for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 10), (10, 100)):
            cell = [r for w, r in tight if lo <= w < hi]
            if cell:
                summarize(cell, f"stop width {lo}-{hi}% of price")

    _e1_report(trades)
    if dump:
        import csv
        cols = ["sym", "entry", "exit", "T", "rule", "capped", "dir", "w", "R", "Rw",
                "ret_pct", "bench", "excess", "ret_atr", "cash", "conf", "straddle",
                "atr_pct", "entry_px", "qty"]
        with open(dump, "w", newline="") as fh:
            wtr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            wtr.writeheader()
            wtr.writerows(trades)
        print(f"\n== B5: dumped {len(trades)} trades x {len(cols)} cols -> {dump} ==")


def _moments(v: list[float]) -> tuple[int, float, float]:
    """n, mean, SE. Returns SE = nan below n=2 rather than raising."""
    n = len(v)
    if n < 2:
        return n, (v[0] if v else float("nan")), float("nan")
    return n, statistics.mean(v), statistics.stdev(v) / math.sqrt(n)


def _contrast(a: list[float], b: list[float], label: str, na: str, nb: str) -> None:
    """⭐ The statistic E1 was missing: the DIFFERENCE with its SE, never two levels.

    §12.27 found that §12.1's positional buckets had never been contrasted at all — the
    published "sign flips at w = 2%" was two point estimates each within 1.3 SE of zero,
    and the contrast is t = −1.47, p = 0.14 with an MDE of 0.74R. That is the family error
    this document has now committed eight times.
    """
    na_, ma, sa = _moments(a)
    nb_, mb, sb = _moments(b)
    if na_ < 2 or nb_ < 2:
        print(f"  {label:<46} (too few)")
        return
    d, se = ma - mb, math.hypot(sa, sb)
    t = d / se if se else float("nan")
    print(f"  {label:<46} {na} {ma:+8.4f}(n{na_})  {nb} {mb:+8.4f}(n{nb_})  "
          f"diff {d:+8.4f}  SE {se:.4f}  t {t:+6.2f}  MDE@80% {2.8016*se:+.3f}")


def _e1_report(trades: list[dict[str, Any]]) -> None:
    """⭐⭐ B5 / E1 — the positional stop-width family in FOUR units, with contrasts.

    Read the three outcome columns against each other. `1/w` amplification is removed by
    moving from R to raw %; the `drift × T` term is removed only by the matched-window
    basket. On the SWING book that sequence took the tight-vs-wide contrast from −0.386
    (t −1.55) to −0.262 (t −0.78) to **+0.069 (t +0.17)** — i.e. the whole family was
    arithmetic. Positional is measured here for the first time, and its prior is NOT the
    swing one: its buckets carry OPPOSITE signs, which `E[ret]·E[1/w]` cannot produce at
    any mean, and its reachable cohort is the BETTER one where swing's is worse.
    """
    if not trades:
        return
    live = [t for t in trades if t["rule"] == "ema" and not t["capped"]]
    print("\n" + "=" * 104)
    print("== B5 / E1: the positional family in FOUR units, with CONTRASTS (not levels) ==")
    print("=" * 104)
    print("  `rule=ema, capped=False` is the LIVE minter's rule (signal_service passes")
    print("  ema20_daily); `flat` is what profiles/pipeline and the backtest actually run.")
    for cohort, rows in (("ALL windows", live),
                         ("gap-clean only", [t for t in live if not t["straddle"]])):
        if len(rows) < 4:
            continue
        print(f"\n  ── {cohort} (n={len(rows)}) ──")
        print(f"  {'bucket':<12} {'n':>4} {'meanT':>6} {'E[1/w]':>7} "
              f"{'R':>9} {'raw %':>9} {'excess %':>9} {'ret/ATR':>9} {'net Rs':>10}")
        for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 10), (10, 1e9)):
            b = [t for t in rows if lo <= t["w"] < hi]
            if len(b) < 2:
                continue
            at = [t["ret_atr"] for t in b if t["ret_atr"] == t["ret_atr"]]
            print(f"  {f'{lo}-{hi if hi < 1e8 else 999}%':<12} {len(b):>4} "
                  f"{statistics.mean([t['T'] for t in b]):>6.2f} "
                  f"{statistics.mean([1 / t['w'] for t in b]):>7.3f} "
                  f"{statistics.mean([t['Rw'] for t in b]):>+9.4f} "
                  f"{statistics.mean([t['ret_pct'] for t in b]):>+9.4f} "
                  f"{statistics.mean([t['excess'] for t in b]):>+9.4f} "
                  f"{statistics.mean(at) if at else float('nan'):>+9.4f} "
                  f"{statistics.mean([t['cash'] for t in b]):>+10.0f}")
        lo_ = [t for t in rows if t["w"] < 2.0]
        hi_ = [t for t in rows if t["w"] >= 2.0]
        for key, nm in (("Rw", "R"), ("ret_pct", "raw %"),
                        ("excess", "excess vs basket %"), ("ret_atr", "ret/ATR20"),
                        ("cash", "net Rs")):
            _contrast([t[key] for t in lo_ if t[key] == t[key]],
                      [t[key] for t in hi_ if t[key] == t[key]],
                      f"  tight(<2%) vs wide(>=2%) in {nm}", "tight", "wide")
    print("\n  ── the gap filter itself, as a contrast ──")
    _contrast([t["Rw"] for t in live if not t["straddle"]],
              [t["Rw"] for t in live if t["straddle"]],
              "  clean vs straddling in R", "clean", "strdl")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=250)
    ap.add_argument("--swing-stride", type=int, default=25,
                    help="0 skips the swing baseline (positional numbers are unchanged)")
    ap.add_argument("--dump-trades", default=None,
                    help="write the per-trade table to this CSV (the B5/round-9 convention: "
                         "one expensive pass, then every contrast is a cheap read)")
    args = ap.parse_args()
    asyncio.run(main(args.stocks, args.swing_stride, args.dump_trades))
