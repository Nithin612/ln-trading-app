"""U11 — a NIFTY buy-and-hold benchmark SERIES aligned to a backtest run's equity curve.

The backtest equity curve is per-TRADE (compounded from each trade's P&L, indexed by trade number)
and `app/backtest/engine.py` is FROZEN, so the curve carries no dates. But every trade in
`trades_json` has an `exit_date`, so each equity point can be dated: point 0 is the window start
(equity 100), and point i (after trade i) is dated at that trade's exit. The benchmark at each
point is NIFTY's indexed level on that date:

    benchmark[i] = NIFTY_close(date_i) / NIFTY_close(window_start) * 100

so the two series start together at 100 and the benchmark's endpoint is the full-window
buy-and-hold return — the H2 comparison ("did it beat doing nothing with the same money").

Fail closed (the `buy_and_hold` philosophy): `available=False` + a `reason` whenever the comparison
cannot be made honestly — the index absent from the registry, no index bars, no bar on or before
the window start, or the run carrying no dated trades. A benchmark that silently substituted a
nearby date or a default index would be worse than none.

Read-only: never writes, never touches scoring/sizing/gating/backtests. Index closes are loaded
once and the per-point lookup is an in-memory as-of (latest close on or before the date) — no
per-point query, and non-trading dates resolve to the prior session's close.
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Index, IndexOhlcvDaily

log = logging.getLogger(__name__)

#: The broad-market baseline — the same constant `buy_and_hold` / `benchmark` fall back to.
BENCHMARK_SYMBOL = "NIFTY50"
_BASIS = 100.0


@dataclass(frozen=True)
class BenchmarkCurve:
    """A benchmark series parallel to a run's `equity_curve`, or an honest unavailability."""

    symbol: str
    available: bool
    reason: str | None
    points: list[float]                 # indexed to 100 at window start; [] when unavailable
    benchmark_return_pct: float | None  # points[-1] - 100
    strategy_return_pct: float | None   # equity_curve[-1] - 100 (independent of availability)


def _parse_date(value: Any) -> date | None:
    """Parse a trades_json ISO date/datetime string (or None) to a `date`. Never raises."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _aligned_point_dates(
    n_points: int, trades: list[dict[str, Any]]
) -> tuple[list[date], date] | None:
    """A date for each of the `n_points` equity points, plus the window start.

    Point 0 is the window start (earliest parseable entry). Point i (i≥1) is trade i-1's exit
    (falling back to its entry, then carrying the previous date so the series is full-length and
    non-decreasing in calendar time). Returns None when no entry date is parseable.
    """
    entry_dates = [d for t in trades if (d := _parse_date(t.get("entry_date"))) is not None]
    if not entry_dates:
        return None
    window_start = min(entry_dates)

    dates: list[date] = [window_start]
    prev = window_start
    for i in range(1, n_points):
        trade = trades[i - 1] if i - 1 < len(trades) else None
        d = None
        if trade is not None:
            d = _parse_date(trade.get("exit_date")) or _parse_date(trade.get("entry_date"))
        if d is None or d < prev:
            d = prev  # carry — never step backwards in calendar time
        dates.append(d)
        prev = d
    return dates, window_start


def _unavailable(reason: str, strategy_return_pct: float | None) -> BenchmarkCurve:
    return BenchmarkCurve(
        symbol=BENCHMARK_SYMBOL, available=False, reason=reason, points=[],
        benchmark_return_pct=None, strategy_return_pct=strategy_return_pct,
    )


async def compute_benchmark_curve(
    db: AsyncSession,
    *,
    equity_curve: list[float] | None,
    trades_json: list[dict[str, Any]] | None,
    symbol: str = BENCHMARK_SYMBOL,
) -> BenchmarkCurve:
    """Build the benchmark series for one run's equity curve. Fails closed (see the docstring)."""
    equity = list(equity_curve or [])
    trades = list(trades_json or [])
    strat_ret = (equity[-1] - _BASIS) if equity else None

    if len(equity) < 2 or not trades:
        return _unavailable("run has no equity curve / dated trades to align against", strat_ret)

    aligned = _aligned_point_dates(len(equity), trades)
    if aligned is None:
        return _unavailable("run trades carry no parseable dates", strat_ret)
    point_dates, window_start = aligned

    index_id = (
        await db.execute(select(Index.id).where(Index.symbol == symbol))
    ).scalar_one_or_none()
    if index_id is None:
        log.warning("benchmark index %s not in the indices registry", symbol)
        return _unavailable(f"benchmark index {symbol} is not in the registry", strat_ret)

    rows = (
        await db.execute(
            select(IndexOhlcvDaily.trade_date, IndexOhlcvDaily.close)
            .where(IndexOhlcvDaily.index_id == index_id)
            .order_by(IndexOhlcvDaily.trade_date)
        )
    ).all()
    if not rows:
        return _unavailable(f"no {symbol} index data for the comparison window", strat_ret)

    idx_dates = [r.trade_date for r in rows]
    idx_closes = [float(r.close) for r in rows]

    def asof(d: date) -> float | None:
        """Latest close on or before `d` (prior-session close on a non-trading date)."""
        i = bisect.bisect_right(idx_dates, d) - 1
        return idx_closes[i] if i >= 0 else None

    basis = asof(window_start)
    if basis is None:
        return _unavailable(
            f"no {symbol} close on or before the window start {window_start.isoformat()}", strat_ret
        )
    if basis == 0.0:
        return _unavailable(f"{symbol} basis close is zero", strat_ret)

    # d ≥ window_start ≥ first index date, so asof never returns None below; guard anyway.
    points = [round(((asof(d) or basis) / basis) * _BASIS, 4) for d in point_dates]

    return BenchmarkCurve(
        symbol=symbol, available=True, reason=None, points=points,
        benchmark_return_pct=round(points[-1] - _BASIS, 4), strategy_return_pct=strat_ret,
    )
