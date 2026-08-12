"""Monthly-return seasonality — read-only context statistic.

Computes, per stock, the historical distribution of *monthly* returns grouped
by calendar month (Jan..Dec) from the already-ingested daily OHLCV
(`ohlcv_1d`). Read-only: no writes, no migration — like `fo_analytics`, it only
aggregates recorded history.

This is a DISCOVERY / CONTEXT statistic, never a signal input. A seasonal bias
is a soft modifier a human reads; it never touches the confluence scorer and
can never mint or alter a trade. **No look-ahead:** only COMPLETED months
strictly before the current IST month are counted (and only `is_complete`
candles), so today's partial month can never leak in. A monthly return is
attributed to the later calendar month and computed ONLY when the immediately
previous calendar month is present, so a data gap never fabricates a
multi-month return.

Sample sizes are reported honestly (`n` per month, `years_covered`): with only
a few years of history a cell can be n=1–5, and the caller must not dress that
up (the StyleStatsHeader precedent).

Returns / percentages = float (analytical, never money); closes = Decimal.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import OhlcvDaily

_IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class MonthSeasonality:
    """Aggregate of one calendar month's returns across all observed years."""

    month: int                       # 1..12
    n: int                           # yearly observations for this month
    positive: int                    # count of up years
    pct_positive: float | None       # share of up years, 0–100 (None when n == 0)
    avg_return_pct: float | None
    median_return_pct: float | None
    best_return_pct: float | None
    worst_return_pct: float | None
    avg_positive_pct: float | None   # mean of up years only (None if none)
    avg_negative_pct: float | None   # mean of down years only (None if none)


@dataclass(frozen=True)
class Seasonality:
    stock_id: int
    months: list[MonthSeasonality]   # always 12, ordered month 1..12
    total_observations: int          # total monthly returns counted
    years_covered: int               # distinct years contributing a return
    first_month: date | None         # earliest completed month with a return
    last_month: date | None          # latest completed month with a return


def _current_ym_ist() -> tuple[int, int]:
    now = datetime.now(tz=_IST)
    return now.year, now.month


async def _month_end_closes(
    db: AsyncSession, stock_id: int
) -> dict[tuple[int, int], Decimal]:
    """(year, month) -> close on the LAST available trading day of that month.

    Completed candles only; the current (partial) IST month and any
    future-dated row are excluded, so a monthly return can never include an
    unfinished month.
    """
    rows = (
        await db.execute(
            select(OhlcvDaily.time, OhlcvDaily.close)
            .where(OhlcvDaily.stock_id == stock_id, OhlcvDaily.is_complete.is_(True))
            .order_by(OhlcvDaily.time)
        )
    ).all()

    cutoff = _current_ym_ist()
    latest: dict[tuple[int, int], tuple[date, Decimal]] = {}
    for ts, close in rows:
        d = ts.astimezone(_IST).date()
        key = (d.year, d.month)
        if key >= cutoff:  # tuple compare: current or future month → skip
            continue
        prev = latest.get(key)
        if prev is None or d > prev[0]:
            latest[key] = (d, close)
    return {k: v[1] for k, v in latest.items()}


def _prev_month(y: int, m: int) -> tuple[int, int]:
    return (y, m - 1) if m > 1 else (y - 1, 12)


async def monthly_seasonality(db: AsyncSession, stock_id: int) -> Seasonality:
    """Per-calendar-month return distribution for a stock (read-only)."""
    closes = await _month_end_closes(db, stock_id)

    by_month: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    ret_keys: list[tuple[int, int]] = []
    for (y, m) in sorted(closes):
        prev_close = closes.get(_prev_month(y, m))
        if prev_close is None or prev_close == 0:
            continue  # no adjacent prior month → don't span a gap
        ret = (float(closes[(y, m)]) / float(prev_close) - 1.0) * 100.0
        by_month[m].append(ret)
        ret_keys.append((y, m))

    months: list[MonthSeasonality] = []
    for m in range(1, 13):
        rs = by_month[m]
        if not rs:
            months.append(
                MonthSeasonality(m, 0, 0, None, None, None, None, None, None, None)
            )
            continue
        ups = [r for r in rs if r > 0]
        downs = [r for r in rs if r < 0]
        months.append(
            MonthSeasonality(
                month=m,
                n=len(rs),
                positive=len(ups),
                pct_positive=len(ups) / len(rs) * 100.0,
                avg_return_pct=statistics.fmean(rs),
                median_return_pct=statistics.median(rs),
                best_return_pct=max(rs),
                worst_return_pct=min(rs),
                avg_positive_pct=statistics.fmean(ups) if ups else None,
                avg_negative_pct=statistics.fmean(downs) if downs else None,
            )
        )

    first = min(ret_keys) if ret_keys else None
    last = max(ret_keys) if ret_keys else None
    return Seasonality(
        stock_id=stock_id,
        months=months,
        total_observations=len(ret_keys),
        years_covered=len({y for (y, _m) in ret_keys}),
        first_month=date(first[0], first[1], 1) if first else None,
        last_month=date(last[0], last[1], 1) if last else None,
    )
