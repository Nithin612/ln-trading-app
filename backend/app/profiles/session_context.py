"""Session-shaped setup context — ONE implementation for both engines.

The intraday setup evaluators (pdh_breakout, opening_gap, top_gainer_925)
need context beyond the price window: the previous session's OHLC and the
9:25 universe cross-section. The walk-forward runner reconstructs these
from historical bars; the live pipeline builds them from the same tables
at run time. Phase-2 lesson (8c-5b): the moment the two sides compute this
context differently, gate outcomes drift between backtest and live — so the
per-symbol math lives HERE and both sides call it (same discipline as the
8b aggregate_trades extraction).

Everything is pure: parallel arrays in (dates are IST session dates, times
are IST tz-aware bar STARTS), plain dicts out. No I/O, no clocks.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time

# The 9:25 screen is born when the 09:20-starting 5m bar has CLOSED.
# Two shared usages (quant-verifier HIGH, 2026-07-07 — look-ahead purge):
#   - bars with start <= this cutoff feed the cross-section (pct_change_at_925);
#   - only decision bars with start >= this cutoff may CONSULT the screen —
#     earlier decisions predate it and must see cross_section=None.
SCREEN_925_READY = time(9, 20)


def session_ohlc(
    dates: Sequence[date],
    open_: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
) -> dict[date, dict[str, float]]:
    """Per-session OHLC, data-driven (half-days come out right because the
    bars, not the clock, decide the session's extent)."""
    out: dict[date, dict[str, float]] = {}
    for i, d in enumerate(dates):
        s = out.get(d)
        if s is None:
            out[d] = {
                "open": open_[i], "high": high[i],
                "low": low[i], "close": close[i],
            }
        else:
            s["high"] = max(s["high"], high[i])
            s["low"] = min(s["low"], low[i])
            s["close"] = close[i]
    return out


def prev_session_map(
    ohlc_by_session: dict[date, dict[str, float]],
) -> dict[date, dict[str, float]]:
    """session → the PREVIOUS present session's OHLC (the earliest session
    has no entry — evaluators fail closed for it, on both engines)."""
    ordered = sorted(ohlc_by_session)
    return {
        d: ohlc_by_session[prev] for prev, d in zip(ordered, ordered[1:], strict=False)
    }


def prev_session_ohlc_for_window(
    dates: Sequence[date],
    open_: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
) -> dict[str, float] | None:
    """Previous-session OHLC for the window's DECISION bar (its last bar),
    or None — the live-pipeline entry point.

    Fails closed (None) when fewer than three sessions are present: with
    exactly two, the previous session is the window's EARLIEST, and a
    bar-count-capped live window (≤300 bars) may have truncated its early
    bars — a PDH/PDL computed from half a session must never gate a
    suggestion (reject, don't approximate). The walk-forward never hits
    this: it loads full sessions since the pinned `since` bound.
    """
    if not dates:
        return None
    ohlc = session_ohlc(dates, open_, high, low, close)
    ordered = sorted(ohlc)
    if len(ordered) < 3:
        return None
    # The decision bar is the last bar, so its session is max(ordered) and
    # the previous session is ordered[-2] — complete by construction, since
    # any cap truncation can only clip ordered[0].
    return ohlc[ordered[-2]]


def pct_change_at_925(
    dates: Sequence[date],
    times: Sequence[datetime],
    closes: Sequence[float],
    cutoff: time = SCREEN_925_READY,
) -> dict[date, float]:
    """Per-session 9:25 %-change for ONE symbol: the close of the last bar
    STARTING at or before `cutoff` (on 5m bars: the 09:20 bar, which closes
    09:25) vs the previous session's final close.

    Sessions with no prior close (first present session) or no early bar
    are absent from the result — the evaluator fails closed for them.
    A zero previous close is skipped rather than divided by.
    `times` must be IST tz-aware bar starts; the cutoff compares naive
    IST time-of-day, exactly as the walk-forward always has.
    """
    out: dict[date, float] = {}
    prev_session_close: float | None = None
    i, n = 0, len(dates)
    while i < n:
        d = dates[i]
        j = i
        early_close: float | None = None
        while j < n and dates[j] == d:
            if times[j].timetz().replace(tzinfo=None) <= cutoff:
                early_close = closes[j]
            j += 1
        if prev_session_close and early_close is not None:
            out[d] = (early_close - prev_session_close) / prev_session_close * 100.0
        prev_session_close = closes[j - 1]
        i = j
    return out
