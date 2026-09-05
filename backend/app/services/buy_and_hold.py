"""Buy-and-hold benchmark for the paper book — H2.

## Why this exists

We report the book's P&L against zero. Zero is the wrong denominator. The question a
trading system has to answer is not "did it make money" but **"did it beat doing nothing
with the same money"** — and the most sobering number in the external review was a
five-year agent project that buy-and-hold quietly beat, invisible until someone opened a
CSV. Our book runs at −0.303R expectancy; the honest comparison is what NIFTY 50 did over
the very same window.

Note this is genuinely absent today rather than merely unreported: `benchmark.py` exists,
but it is per-signal relative strength for the sector-RS overlay, not a portfolio baseline.

## What is compared, and the one asymmetry to keep in view

  book      = realised P&L since the paper clock started **plus** the open book's
              mark-to-market, over capital. Open positions are included deliberately: a
              book sitting on a large unrealised loss would otherwise flatter itself
              against an index that is marked every day.
  benchmark = NIFTY 50 close-to-close over the same dates, as a percentage.

**They are not deployed alike, and the report says so rather than adjusting for it.**
Buy-and-hold is 100% invested; our sampler risks ~₹2k per trade and sits well under full
deployment. A "leverage-adjusted" version would be a modelling choice dressed as a fact,
so the exposure figure is printed beside the two returns and the reader draws the line.
The unadjusted comparison is still the one that matters — it is the question an investor
actually faces with a fixed sum of money.

## Fail closed

`None` whenever the comparison cannot be made honestly: no paper clock (nothing defines
the window), no index bar at either end, or a zero capital figure. A benchmark line that
silently substitutes a nearby date or a default index would be worse than no line at all,
because its whole purpose is to be the number nobody can argue with.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratios import safe_ratio
from app.models.stock import Index, IndexOhlcvDaily

log = logging.getLogger(__name__)

#: The broad-market baseline. Same constant `benchmark.py` falls back to.
BENCHMARK_SYMBOL = "NIFTY50"

_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class BuyAndHold:
    """The book against doing nothing, over identical dates."""

    index_symbol: str
    start: date  # the bar actually used, not the requested date
    end: date
    index_start_close: Decimal
    index_end_close: Decimal
    index_return_pct: Decimal
    book_pnl: Decimal  # realised over the window + open mark-to-market
    capital: Decimal
    book_return_pct: Decimal

    @property
    def excess_pct(self) -> Decimal:
        """Book minus benchmark. Positive = the trading added something."""
        return self.book_return_pct - self.index_return_pct


async def _bar_on_or_before(
    db: AsyncSession, index_id: int, day: date
) -> tuple[date, Decimal] | None:
    """The latest index close on or before `day`.

    On-or-before, not exact: the paper clock can start on a weekend or a holiday, and the
    honest baseline is the last price you could actually have bought at. It never reaches
    FORWARD, which would be look-ahead.
    """
    row = (
        await db.execute(
            select(IndexOhlcvDaily.trade_date, IndexOhlcvDaily.close)
            .where(IndexOhlcvDaily.index_id == index_id, IndexOhlcvDaily.trade_date <= day)
            .order_by(IndexOhlcvDaily.trade_date.desc())
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def compare(
    db: AsyncSession,
    *,
    start: date,
    end: date,
    book_pnl: Decimal,
    capital: Decimal,
    index_symbol: str = BENCHMARK_SYMBOL,
) -> BuyAndHold | None:
    """Book vs buy-and-hold over `start`→`end`. ``None`` when it cannot be made honestly."""
    if capital <= 0 or start > end:
        return None
    index_id = (
        await db.execute(select(Index.id).where(Index.symbol == index_symbol))
    ).scalar()
    if index_id is None:
        return None
    first = await _bar_on_or_before(db, index_id, start)
    last = await _bar_on_or_before(db, index_id, end)
    if first is None or last is None or first[0] == last[0]:
        # Same bar at both ends = a window shorter than one session. A 0.0% benchmark
        # there is not a fact about the market, it is an artefact of the window.
        return None

    index_return = safe_ratio((last[1] - first[1]) * _HUNDRED, first[1])
    book_return = safe_ratio(book_pnl * _HUNDRED, capital)
    if index_return is None or book_return is None:
        return None
    return BuyAndHold(
        index_symbol=index_symbol,
        start=first[0],
        end=last[0],
        index_start_close=first[1],
        index_end_close=last[1],
        index_return_pct=index_return,
        book_pnl=book_pnl,
        capital=capital,
        book_return_pct=book_return,
    )


def render_lines(r: BuyAndHold | None, *, exposure_pct: Decimal | None = None) -> list[str]:
    """One block for the daily report, under the scorecard."""
    if r is None:
        return [
            "- **vs buy-and-hold:** not assessable (needs a paper-clock start, a capital "
            "figure, and NIFTY 50 bars at both ends of the window)"
        ]
    verdict = "**BEAT** buy-and-hold" if r.excess_pct > 0 else "**LOST TO** buy-and-hold"
    out = [
        f"- **vs buy-and-hold ({r.index_symbol}, {r.start} → {r.end}):** the book "
        f"{verdict} by **{r.excess_pct:+.2f} pp**",
        f"  - book {r.book_return_pct:+.2f}% (₹{r.book_pnl:,.0f} realised + open MTM on "
        f"₹{r.capital:,.0f}) · {r.index_symbol} {r.index_return_pct:+.2f}% "
        f"({r.index_start_close:,.2f} → {r.index_end_close:,.2f})",
    ]
    if exposure_pct is not None:
        out.append(
            f"  - ⚠ not deployed alike: buy-and-hold is 100% invested, this book carries "
            f"{exposure_pct:.1f}% of capital at risk. The gap is NOT adjusted for — an "
            "adjustment would be a modelling choice dressed as a fact — but which way it "
            f"cuts depends on the signs: {_deployment_note(r)}"
        )
    return out


def _deployment_note(r: BuyAndHold) -> str:
    """Which way partial deployment cuts, given the two signs.

    It does not always excuse a shortfall, and a fixed sentence saying it does would be
    exactly the kind of misleading line this report exists to prevent — the same lesson
    `flip_readiness.tail_guard` learned when it announced "the negative mean is carried by
    losses" for a cohort whose mean was positive.
    """
    if r.excess_pct > 0:
        return (
            "the book is AHEAD while holding less at risk, so full deployment would likely "
            "have widened the lead — the result is stronger than the headline, not weaker"
        )
    if r.index_return_pct > 0:
        return (
            "the index ROSE and the book trailed it, so being under-deployed genuinely "
            "explains part of the gap — an uninvested rupee cannot capture a rally"
        )
    return (
        "the index FELL and the book fell further, so under-deployment makes this WORSE, "
        "not better: less capital was exposed and more was still lost. Partial deployment "
        "is no defence here"
    )
