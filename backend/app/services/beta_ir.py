"""Beta to NIFTY and the information ratio — H12.

## Why this exists

On 4,843 published replications the median strategy carries **beta +0.17**, and stripping
that market exposure takes the median information ratio to **0.21** — roughly halving the
apparent edge. We compute **no beta and no IR anywhere**, which leaves one specific
blindness: *a cohort that is directionally biased in a trending market looks like skill.*

We have already been bitten by exactly that. The market-regime gate's evidence turned out
to be a **proxy for side** — NIFTY sat below its 200-DMA on 33 of 33 days, so every LONG
was blocked and every SHORT kept, and "would-block is net-negative" was just *our longs
lost and our shorts broke even over one directional window*. `flip_readiness.side_proxy_guard`
catches the extreme version by counting sides. Beta catches the graded version, by pricing
how much of a cohort's return is simply the market showing up.

This is the third robustness axis beside **H1** (is it stable under resampling?) and
**H8** (does the bar reject noise?): **is it just the market?**

## The construction

For each closed trade, the market return over that trade's own holding window, **signed by
side**:

    market_r = side_sign × (index_close[exit] / index_close[entry] − 1)

The sign is the whole point. A short that profits while the index falls is collecting
market exposure, not skill — unsigned, it would look like negative beta and flatter the
cohort. Then an ordinary least-squares fit of trade return on market return:

    beta  = cov(trade, market) / var(market)
    alpha = mean(trade) − beta × mean(market)      (per trade, not annualised)
    IR    = alpha / stdev(residual)

`beta ≈ 0` means the cohort's outcome is unexplained by the market — which is what a real
edge looks like. A large positive beta on a long-biased cohort in a rising window means the
result would have happened without any signal at all.

## First read on the live book (2026-09-05)

105 closed paper positions, return measured as `realized_pnl ÷ notional`, market signed
by side:

    all trades   n=105  beta +0.638   alpha +0.607%/trade   IR +0.133
    LONG         n= 69  beta +0.342   alpha +0.696%/trade   IR +0.143
    SHORT        n= 36  beta +1.492   alpha +0.188%/trade   IR +0.048

Two things worth carrying forward. **Our beta is far above the +0.17 published median**,
and the shorts carry most of it (+1.49) — over a window whose mean signed market move was
−0.35%, so the market cost the book −0.225%/trade and is not what sank it.

And a discrepancy the instrument surfaced rather than resolved: **equal-weighted return per
trade is +0.382% while the capital-weighted return is −0.118%.** The tempting reading is
"big positions pick worse", and it is **wrong** — Spearman(notional, return%) is **−0.061**,
essentially zero. The largest quartile's mean return is *positive* (+0.084%) while its rupee
total is **−₹25,404**: a few large-notional losers dominate in rupees. So the sign flip is
**concentration, not selection**. Note the top quartile's median notional is **₹122,566** on
₹100,000 of capital — these are rows predating the per-position notional cap, which is
exactly the shape that cap exists to prevent.

## Honest limits

- **Per-trade, not time-weighted.** Each trade contributes one (market, trade) pair
  regardless of how long it was held, so a 1-day and a 20-day hold weigh the same. Correct
  for judging *signals*; it is not a portfolio beta and must not be reported as one.
- Overlapping holding periods share market moves, so the residuals are correlated and the
  IR is optimistic in the same way DSR is. Read it beside H1's interval, not alone.
- Needs `MIN_TRADES` pairs and non-zero market variance. In a window where the index barely
  moved, beta is not estimable and the honest answer is ``None``, not zero.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.core.ratios import safe_ratio_f

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

#: Below this an OLS slope on our data is a line through noise.
MIN_TRADES = 10


@dataclass(frozen=True)
class Trade:
    """One closed trade, reduced to what a beta needs."""

    entry_day: date
    exit_day: date
    side: str  # "LONG" | "SHORT"
    #: The trade's own **fractional** return — e.g. `realized_pnl ÷ (entry × qty)`.
    #: ⚠ NOT a currency amount. Beta is cov(trade, market) / var(market), so feeding ₹
    #: against a fractional market move yields a beta carrying units of ₹-per-unit-market
    #: (measured at −12,561 on the real book) which is arithmetically fine and completely
    #: incomparable to the published +0.17 median this finding is calibrated against.
    #: Fractional in, dimensionless out.
    ret: float


@dataclass(frozen=True)
class BetaIr:
    n: int
    beta: float
    alpha: float  # per trade, in the units of `Trade.ret`
    #: None when the residuals have zero spread — a PERFECT fit (every trade exactly its
    #: market move, or every trade the same constant) has no residual to divide by. Beta
    #: and alpha are still well defined there, and they are the primary outputs, so the
    #: undefined ratio must not discard them. Found by test: returning None for the whole
    #: result threw away a beta of exactly 1.0 on a pure market follower.
    information_ratio: float | None
    market_mean: float  # mean signed market return over the same windows
    explained_by_market: float  # beta × market_mean — the part that is not skill

    @property
    def is_market_driven(self) -> bool:
        """True when the market explains at least half of the cohort's mean return, in
        the same direction. The graded version of the side-proxy veto."""
        total = self.alpha + self.explained_by_market
        if total == 0:
            return False
        share = self.explained_by_market / total
        return share >= 0.5


def _signed_market_return(
    t: Trade, closes: Mapping[date, float]
) -> float | None:
    """Market return over this trade's window, signed by side. ``None`` when either end
    has no index bar — never substituted, since a wrong window is a wrong beta."""
    a = closes.get(t.entry_day)
    b = closes.get(t.exit_day)
    if a is None or b is None or a <= 0:
        return None
    raw = (b / a) - 1.0
    return raw if t.side.upper() == "LONG" else -raw


def compute(trades: Sequence[Trade], closes: Mapping[date, float]) -> BetaIr | None:
    """OLS of trade return on signed market return. ``None`` when not estimable."""
    pairs: list[tuple[float, float]] = []
    for t in trades:
        m = _signed_market_return(t, closes)
        if m is not None:
            pairs.append((m, t.ret))
    if len(pairs) < MIN_TRADES:
        return None

    mkt = [p[0] for p in pairs]
    trd = [p[1] for p in pairs]
    var_m = statistics.pvariance(mkt)
    if var_m <= 0:
        # A window in which the index did not move cannot identify a slope. Zero would be
        # a claim ("no market exposure"); None is the truth ("not estimable here").
        return None
    m_bar = statistics.fmean(mkt)
    t_bar = statistics.fmean(trd)
    cov = sum((m - m_bar) * (r - t_bar) for m, r in pairs) / len(pairs)
    beta = cov / var_m
    alpha = t_bar - beta * m_bar

    residuals = [r - (alpha + beta * m) for m, r in pairs]
    sd = statistics.stdev(residuals) if len(residuals) > 1 else 0.0
    # `None` IR, not a dropped result — see the field's note.
    ir = safe_ratio_f(alpha, sd)
    return BetaIr(
        n=len(pairs),
        beta=beta,
        alpha=alpha,
        information_ratio=ir,
        market_mean=m_bar,
        explained_by_market=beta * m_bar,
    )


async def load_closed_trades(
    db: AsyncSession, *, user_id: int, since: datetime | None = None
) -> list[Trade]:
    """Closed paper positions as fractional-return trades, IST trade dates.

    Return is `realized_pnl ÷ (entry × qty)` — the money that trade actually tied up — so
    beta comes out dimensionless (see `Trade.ret`). Rows without a usable notional are
    skipped rather than defaulted: a fabricated denominator is a fabricated beta.
    """
    from sqlalchemy import text

    sql = """
        SELECT (p.opened_at AT TIME ZONE 'Asia/Kolkata')::date AS entry_day,
               (p.closed_at AT TIME ZONE 'Asia/Kolkata')::date AS exit_day,
               p.side, p.realized_pnl, p.avg_entry_price, p.quantity
        FROM positions p
        WHERE p.mode = 'paper'
          AND p.closed_at IS NOT NULL
          AND p.realized_pnl IS NOT NULL
          AND p.avg_entry_price > 0
          AND p.quantity > 0
          AND p.user_id = :user_id
          {since}
        ORDER BY p.opened_at
    """.format(since="AND p.closed_at >= :since" if since is not None else "")
    params: dict[str, object] = {"user_id": user_id}
    if since is not None:
        params["since"] = since
    rows = (await db.execute(text(sql), params)).all()
    out: list[Trade] = []
    for r in rows:
        notional = float(r.avg_entry_price) * int(r.quantity)
        if notional <= 0:
            continue
        out.append(
            Trade(
                entry_day=r.entry_day,
                exit_day=r.exit_day,
                side=str(r.side),
                ret=float(r.realized_pnl) / notional,
            )
        )
    return out


async def load_index_closes(
    db: AsyncSession, *, symbol: str = "NIFTY50"
) -> dict[date, float]:
    """`{trade_date: close}` for one index. Empty when the index is unknown — the caller
    then reports "not assessable" rather than a beta against nothing."""
    from sqlalchemy import select

    from app.models.stock import Index, IndexOhlcvDaily

    index_id = (await db.execute(select(Index.id).where(Index.symbol == symbol))).scalar()
    if index_id is None:
        return {}
    rows = (
        await db.execute(
            select(IndexOhlcvDaily.trade_date, IndexOhlcvDaily.close).where(
                IndexOhlcvDaily.index_id == index_id
            )
        )
    ).all()
    return {r[0]: float(r[1]) for r in rows}


def render_lines(r: BetaIr | None, *, label: str) -> list[str]:
    """One block per cohort evaluation — beside H1's interval and the DSR bar."""
    if r is None:
        return [
            f"- **{label} — beta / IR:** not assessable (needs ≥{MIN_TRADES} trades with "
            "index bars at both ends, and a window in which the index actually moved)"
        ]
    flag = " ⚠ **MARKET-DRIVEN**" if r.is_market_driven else ""
    ir = f"{r.information_ratio:+.3f}" if r.information_ratio is not None else "— (perfect fit)"
    return [
        f"- **{label} — market exposure:** beta **{r.beta:+.2f}** · "
        f"per-trade alpha **{r.alpha:+.4f}** · IR **{ir}**{flag}",
        f"  - of the cohort's mean outcome, {r.explained_by_market:+.4f} is explained by "
        f"the market (signed by side; mean market move {r.market_mean:+.2%}) and "
        f"{r.alpha:+.4f} is not",
        "  - ⚠ per-TRADE beta, not a portfolio beta — every trade weighs the same "
        "regardless of holding period; and overlapping holds share market moves, so the "
        "IR is optimistic in the same way DSR is.",
    ]
