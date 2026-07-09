"""Setup-condition evaluators (Phase 2 slice 5).

Per the adjudicated Phase-2 design: setups are profile-level ENTRY GATES
layered on top of the frozen 14-factor confluence engine. They can only
DROP a confluence-passed suggestion, never mint one — the ≥70% gate always
decides first (trading-domain.md "confluence only").

Every evaluator is a pure function `(window, params, ctx) -> SetupVerdict`
shared verbatim between the live pipeline (slice 7) and the walk-forward
runner (slice 8), so backtest and live can't diverge. Evaluators that need
information beyond the price window (benchmark series, factor snapshot,
9:25 cross-section) read it from SetupContext and FAIL CLOSED (passed=False
with a reason) when it is missing — reject-don't-clamp.

Direction-awareness: a setup gates the signal the confluence engine
produced, so evaluators receive ctx.direction and check the side that
confirms it (e.g. pdh_breakout: BUY → close above previous day's high,
SELL → close below previous day's low).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from app.schemas.profile import KNOWN_SETUP_TYPES

_IST = ZoneInfo("Asia/Kolkata")


def _ist_date(ts: pd.Timestamp) -> date:
    """IST session date of a bar. Walk-forward indexes are already IST and
    live indexes are UTC — for NSE session bars both give the same calendar
    date, but converting explicitly removes the coincidence dependency
    (quant-verifier note, 2026-07-09). Naive stamps pass through."""
    d: date = ts.astimezone(_IST).date() if ts.tzinfo is not None else ts.date()
    return d


@dataclass
class SetupContext:
    """Everything an evaluator may need beyond the price window."""

    direction: str  # "BUY" | "SELL" — from the confluence result
    # {factor_name: (weight, score)} snapshot of the scored window
    factors: dict[str, tuple[float, float]] | None = None
    # benchmark close series (NIFTY50) date-aligned to the window
    benchmark_closes: pd.Series | None = None
    # previous day's OHLC for intraday windows ({open,high,low,close});
    # on 1d windows evaluators derive it from window.iloc[-2] instead
    prev_day: dict[str, float] | None = None
    # 9:25 cross-section: {symbol: pct_change_since_prev_close}
    cross_section: dict[str, float] | None = None
    symbol: str | None = None


@dataclass
class SetupVerdict:
    passed: bool
    context: dict[str, Any] = field(default_factory=dict)


Evaluator = Callable[[pd.DataFrame, dict[str, Any], SetupContext], SetupVerdict]


def _is_intraday_window(window: pd.DataFrame) -> bool:
    """Sub-session bar spacing ⇒ intraday window. Data-driven: the smallest
    gap between consecutive bars decides (a real 5m/15m/1h window always
    contains sub-hour gaps; daily windows never do). Non-datetime indexes
    are treated as daily — the historical unit-fixture shape."""
    if not isinstance(window.index, pd.DatetimeIndex) or len(window) < 2:
        return False
    return bool((window.index[1:] - window.index[:-1]).min() <= pd.Timedelta(hours=1))


def _prev_day_hlc(window: pd.DataFrame, ctx: SetupContext) -> dict[str, float] | None:
    """Previous session's OHLC: ctx.prev_day when provided, else derived
    from the second-to-last row of a DAILY window.

    An intraday window without ctx.prev_day FAILS CLOSED (None): its
    iloc[-2] is the previous BAR, not the previous day, and gating a
    "PDH breakout" on a five-minute range would pass almost everything
    (quant-verifier MEDIUM, 2026-07-07 — Phase-3 pre-work)."""
    if ctx.prev_day is not None:
        return ctx.prev_day
    if len(window) < 2 or _is_intraday_window(window):
        return None
    prev = window.iloc[-2]
    return {
        "open": float(prev["open"]),
        "high": float(prev["high"]),
        "low": float(prev["low"]),
        "close": float(prev["close"]),
    }


def _session_open(window: pd.DataFrame) -> float:
    """The decision session's opening price: on intraday windows the FIRST
    bar of the last session (the last row's open is mid-session once the
    session is underway); on daily windows the last row's open."""
    if _is_intraday_window(window):
        session_date = _ist_date(window.index[-1])
        todays = window[[_ist_date(ts) == session_date for ts in window.index]]
        return float(todays["open"].iloc[0])
    return float(window["open"].iloc[-1])


def eval_pdh_breakout(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Previous-day-extreme momentum: BUY → close > PDH; SELL → close < PDL."""
    prev = _prev_day_hlc(window, ctx)
    if prev is None:
        return SetupVerdict(False, {"reason": "no previous session available"})
    close = float(window["close"].iloc[-1])
    if ctx.direction == "BUY":
        passed = close > prev["high"]
        return SetupVerdict(passed, {"close": close, "pdh": prev["high"]})
    passed = close < prev["low"]
    return SetupVerdict(passed, {"close": close, "pdl": prev["low"]})


def eval_pdl_breakdown(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Strict short-side variant: only SELL signals may pass."""
    if ctx.direction != "SELL":
        return SetupVerdict(False, {"reason": "short-only setup on a BUY signal"})
    prev = _prev_day_hlc(window, ctx)
    if prev is None:
        return SetupVerdict(False, {"reason": "no previous session available"})
    close = float(window["close"].iloc[-1])
    return SetupVerdict(close < prev["low"], {"close": close, "pdl": prev["low"]})


def eval_opening_gap(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Opening gap in the signal's direction, ≥ min_gap_pct (default 2%).

    The gap is measured at the SESSION open (intraday windows use the
    decision session's first bar — the last row's open is mid-session and
    was silently standing in for it before the Phase-3 pre-work fix)."""
    min_gap_pct = float(params.get("min_gap_pct", 2.0))
    prev = _prev_day_hlc(window, ctx)
    if prev is None or prev["close"] == 0:
        return SetupVerdict(False, {"reason": "no previous session available"})
    open_ = _session_open(window)
    gap_pct = (open_ - prev["close"]) / prev["close"] * 100.0
    if ctx.direction == "BUY":
        passed = gap_pct >= min_gap_pct
    else:
        passed = gap_pct <= -min_gap_pct
    return SetupVerdict(passed, {"gap_pct": round(gap_pct, 4), "min_gap_pct": min_gap_pct})


def eval_relative_strength(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Stock return minus benchmark return over `lookback` sessions must
    exceed min_excess_pct in the signal's direction (BUY: outperformance,
    SELL: underperformance)."""
    lookback = int(params.get("lookback", 20))
    min_excess_pct = float(params.get("min_excess_pct", 0.0))
    if ctx.benchmark_closes is None or len(ctx.benchmark_closes) < lookback + 1:
        return SetupVerdict(False, {"reason": "benchmark series unavailable"})
    if len(window) < lookback + 1:
        return SetupVerdict(False, {"reason": "window shorter than lookback"})

    stock_now = float(window["close"].iloc[-1])
    stock_then = float(window["close"].iloc[-(lookback + 1)])
    bench_now = float(ctx.benchmark_closes.iloc[-1])
    bench_then = float(ctx.benchmark_closes.iloc[-(lookback + 1)])
    if stock_then == 0 or bench_then == 0:
        return SetupVerdict(False, {"reason": "degenerate base price"})

    stock_ret = (stock_now - stock_then) / stock_then * 100.0
    bench_ret = (bench_now - bench_then) / bench_then * 100.0
    excess = stock_ret - bench_ret
    passed = excess >= min_excess_pct if ctx.direction == "BUY" else excess <= -min_excess_pct
    return SetupVerdict(
        passed,
        {
            "stock_ret_pct": round(stock_ret, 4),
            "bench_ret_pct": round(bench_ret, 4),
            "excess_pct": round(excess, 4),
            "lookback": lookback,
        },
    )


def eval_factor_score(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Gate on a confluence factor's score from the scored window snapshot —
    how RRBO/multibagger profiles bind to existing detection without
    re-implementing it. BUY requires score ≥ +min_score, SELL ≤ −min_score."""
    name = str(params.get("factor", ""))
    min_score = float(params.get("min_score", 0.5))
    if not ctx.factors or name not in ctx.factors:
        return SetupVerdict(False, {"reason": f"factor {name!r} not in snapshot"})
    _, score = ctx.factors[name]
    passed = score >= min_score if ctx.direction == "BUY" else score <= -min_score
    return SetupVerdict(passed, {"factor": name, "score": score, "min_score": min_score})


def eval_dc1(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """DC1 (§2.5): price at a demand/supply zone with a reversal pattern —
    exactly what the SR_ZONE factor scores at ±0.85+. Sugar over
    factor_score so the masterclass name reads directly in profiles."""
    return eval_factor_score(
        window, {"factor": "SR_ZONE", "min_score": float(params.get("min_score", 0.85))}, ctx
    )


def eval_dc2(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """DC2: DC1 on the PREVIOUS candle plus a confirmation candle now
    (BUY: close above previous high; SELL: close below previous low).

    Recomputes the S/R-zone factor on the window minus the last candle —
    one extra factor call, no look-ahead (both windows end at or before the
    decision candle).
    """
    if len(window) < 3:
        return SetupVerdict(False, {"reason": "window too short for DC2"})

    from app.analysis.structure.levels import sr_zone_factor

    min_score = float(params.get("min_score", 0.85))
    prior = window.iloc[:-1]
    bullish = ctx.direction == "BUY"
    prior_factor = sr_zone_factor(
        prior,
        current_price=float(prior["close"].iloc[-1]),
        bullish_pattern=bullish,
        bearish_pattern=not bullish,
        breakout_volume_ok=False,
    )
    dc1_then = (
        prior_factor.score >= min_score if bullish else prior_factor.score <= -min_score
    )
    if not dc1_then:
        return SetupVerdict(
            False, {"reason": "no DC1 on prior candle", "prior_sr_score": prior_factor.score}
        )

    close = float(window["close"].iloc[-1])
    prev = window.iloc[-2]
    confirmed = close > float(prev["high"]) if bullish else close < float(prev["low"])
    return SetupVerdict(
        confirmed,
        {
            "prior_sr_score": prior_factor.score,
            "close": close,
            "confirm_level": float(prev["high"]) if bullish else float(prev["low"]),
        },
    )


def eval_orb_breakout(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """Opening-range breakout (intraday-only). The window must be
    session-aligned intraday bars of the CURRENT session; the opening range
    is the first `or_minutes` of the session. Fails closed on daily data."""
    or_minutes = int(params.get("or_minutes", 15))
    if not isinstance(window.index, pd.DatetimeIndex) or len(window) < 2:
        return SetupVerdict(False, {"reason": "requires intraday session bars"})

    # bar spacing > 1h ⇒ this is daily data, not an intraday session
    spacing = window.index[-1] - window.index[-2]
    if spacing > pd.Timedelta(hours=1):
        return SetupVerdict(False, {"reason": "requires intraday session bars"})

    session_date = _ist_date(window.index[-1])
    todays = window[[_ist_date(ts) == session_date for ts in window.index]]
    if todays.empty:
        return SetupVerdict(False, {"reason": "no bars for current session"})
    session_open = todays.index[0]
    or_bars = todays[todays.index < session_open + pd.Timedelta(minutes=or_minutes)]
    after = todays[todays.index >= session_open + pd.Timedelta(minutes=or_minutes)]
    if or_bars.empty or after.empty:
        return SetupVerdict(False, {"reason": "opening range not yet complete"})

    or_high = float(or_bars["high"].max())
    or_low = float(or_bars["low"].min())
    close = float(window["close"].iloc[-1])
    passed = close > or_high if ctx.direction == "BUY" else close < or_low
    return SetupVerdict(
        passed, {"or_high": or_high, "or_low": or_low, "close": close, "or_minutes": or_minutes}
    )


def eval_top_gainer_925(
    window: pd.DataFrame, params: dict[str, Any], ctx: SetupContext
) -> SetupVerdict:
    """9:25 AM screen: stock must be among the session's top `top_n`
    gainers (BUY) / losers (SELL) in the profile universe cross-section."""
    top_n = int(params.get("top_n", 10))
    if not ctx.cross_section or ctx.symbol is None:
        return SetupVerdict(False, {"reason": "9:25 cross-section unavailable"})
    if ctx.symbol not in ctx.cross_section:
        return SetupVerdict(False, {"reason": "symbol missing from cross-section"})

    # Deterministic tie-break by symbol: a stable sort on pct alone kept
    # dict-insertion order, which differs between live (planner row order)
    # and walk-forward (alphabetical) — exact-tie gate outcomes could
    # drift between the two (bug-hunter LOW, 2026-07-09).
    buy_side = ctx.direction == "BUY"
    ranked = sorted(
        ctx.cross_section.items(),
        key=lambda kv: ((-kv[1] if buy_side else kv[1]), kv[0]),
    )
    top = {sym for sym, _ in ranked[:top_n]}
    change = ctx.cross_section[ctx.symbol]
    correct_sign = change > 0 if ctx.direction == "BUY" else change < 0
    return SetupVerdict(
        ctx.symbol in top and correct_sign,
        {"pct_change_925": change, "top_n": top_n},
    )


SETUP_EVALUATORS: dict[str, Evaluator] = {
    "pdh_breakout": eval_pdh_breakout,
    "pdl_breakdown": eval_pdl_breakdown,
    "opening_gap": eval_opening_gap,
    "relative_strength": eval_relative_strength,
    "dc1": eval_dc1,
    "dc2": eval_dc2,
    "orb_breakout": eval_orb_breakout,
    "top_gainer_925": eval_top_gainer_925,
    "factor_score": eval_factor_score,
}

# schemas/profile.py validates setup types against KNOWN_SETUP_TYPES; this
# import-time raise (plus a test) keeps the two sets from drifting silently.
if set(SETUP_EVALUATORS) != KNOWN_SETUP_TYPES:  # pragma: no cover
    raise RuntimeError(
        "SETUP_EVALUATORS and schemas.profile.KNOWN_SETUP_TYPES have drifted: "
        f"{set(SETUP_EVALUATORS) ^ KNOWN_SETUP_TYPES}"
    )


def evaluate_conditions(
    conditions: list[dict[str, Any]],
    window: pd.DataFrame,
    ctx: SetupContext,
) -> tuple[bool, dict[str, Any]]:
    """AND-evaluate a profile's setup_conditions.

    Returns (all_passed, evidence) where evidence maps each evaluated
    condition type to its verdict context — persisted as Signal.setup_trigger
    so the UI/journal can show WHY a suggestion fired. Evaluation
    short-circuits on the first failure (its evidence is included).
    """
    evidence: dict[str, Any] = {}
    for cond in conditions:
        ctype = str(cond["type"])
        evaluator = SETUP_EVALUATORS.get(ctype)
        if evaluator is None:
            # schema validation makes this unreachable; fail closed anyway
            return False, {ctype: {"reason": "unknown setup type"}}
        verdict = evaluator(window, dict(cond.get("params", {})), ctx)
        evidence[ctype] = {"passed": verdict.passed, **verdict.context}
        if not verdict.passed:
            return False, evidence
    return True, evidence
