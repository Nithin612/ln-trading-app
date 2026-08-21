"""Market-regime diagnostic — the tape context the two-window autopsy (04–12 vs 13–21 Aug) showed
matters MORE than the 200-DMA level alone.

NIFTY was below its 200-DMA in BOTH windows, yet one was +₹16k and the other −₹8k; what separated
them was short-term **breadth / slope** (4/4 up-days vs 1/7), not the level. So this report shows
NIFTY vs its 200-DMA AND vs its 20-DMA (trend), the breadth (% up-days over the last N sessions),
the short-run return, and VIX — and **flags when the LEVEL and the BREADTH disagree** (below 200-DMA
but strong breadth = the profitable Window A; below AND weak = the losing Window B). Read-only.

The pure `summarize_regime` takes the close series + VIX so it is unit-testable without a DB; the
`compute_market_regime` wrapper loads them via `benchmark.load_market_regime_context` (no look-ahead
— closes are anchored to `as_of`).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.benchmark import load_market_regime_context

_DMA_LONG = 200
_DMA_SHORT = 20
_BREADTH_WINDOW = 10  # sessions of up/down breadth (needs BREADTH_WINDOW+1 closes)


@dataclass(frozen=True)
class RegimeSummary:
    market_symbol: str
    enough: bool  # False ⇒ too few closes to assess; other fields are None
    sessions: int = 0
    note: str | None = None
    last_close: float | None = None
    dma_long: float | None = None
    dma_short: float | None = None
    vs_long_pct: float | None = None  # % of last close above/below the 200-DMA
    vs_short_pct: float | None = None  # ... above/below the 20-DMA
    breadth_up_pct: float | None = None  # % of the last N sessions that closed up
    breadth_window: int = _BREADTH_WINDOW
    short_return_pct: float | None = None  # return over the breadth window
    vix: float | None = None
    level_bullish: bool | None = None  # above the 200-DMA
    breadth_bullish: bool | None = None  # breadth ≥ 50% AND above the 20-DMA
    disagree: bool | None = None  # level and breadth point opposite ways


def summarize_regime(
    closes: list[Decimal],
    vix: Decimal | None,
    *,
    market_symbol: str = "NIFTY 50",
    dma_long: int = _DMA_LONG,
    dma_short: int = _DMA_SHORT,
    breadth_window: int = _BREADTH_WINDOW,
) -> RegimeSummary:
    """Level (vs 200-DMA) + breadth (% up-days, vs 20-DMA) + VIX, with a disagreement flag. Closes
    are chronological (oldest→newest). Fails gracefully when history is too short."""
    n = len(closes)
    if n < breadth_window + 1 or n < dma_short:
        return RegimeSummary(
            market_symbol=market_symbol,
            enough=False,
            sessions=n,
            note=f"only {n} closes — need ≥ {max(breadth_window + 1, dma_short)} to assess",
        )
    c = [float(x) for x in closes]
    last = c[-1]
    dma_long_val = statistics.mean(c[-dma_long:])  # partial (all available) if n < dma_long
    dma_short_val = statistics.mean(c[-dma_short:])
    vs_long = (last / dma_long_val - 1) * 100 if dma_long_val else 0.0
    vs_short = (last / dma_short_val - 1) * 100 if dma_short_val else 0.0
    win = c[-(breadth_window + 1):]
    ups = sum(1 for a, b in zip(win, win[1:], strict=False) if b > a)
    breadth_up = ups / breadth_window * 100
    short_return = (win[-1] / win[0] - 1) * 100 if win[0] else 0.0
    level_bullish = vs_long >= 0
    breadth_bullish = breadth_up >= 50.0 and vs_short >= 0
    partial = " (200-DMA on a partial window)" if n < dma_long else ""
    return RegimeSummary(
        market_symbol=market_symbol,
        enough=True,
        sessions=n,
        note=(f"{n} closes{partial}"),
        last_close=last,
        dma_long=dma_long_val,
        dma_short=dma_short_val,
        vs_long_pct=vs_long,
        vs_short_pct=vs_short,
        breadth_up_pct=breadth_up,
        breadth_window=breadth_window,
        short_return_pct=short_return,
        vix=float(vix) if vix is not None else None,
        level_bullish=level_bullish,
        breadth_bullish=breadth_bullish,
        disagree=level_bullish != breadth_bullish,
    )


async def compute_market_regime(
    db: AsyncSession, *, as_of: datetime | None = None
) -> RegimeSummary:
    ctx = await load_market_regime_context(db, dma_period=_DMA_LONG, as_of=as_of)
    return summarize_regime(ctx.market_closes, ctx.vix, market_symbol=ctx.market_symbol)


def summary_line(r: RegimeSummary) -> str:
    if not r.enough:
        return f"[market regime] insufficient index history — {r.note}"
    flag = " ⚠ LEVEL vs BREADTH DISAGREE" if r.disagree else ""
    vix = f"{r.vix:.1f}" if r.vix is not None else "n/a"
    return (
        f"[market regime] {r.market_symbol} {r.vs_long_pct:+.1f}% vs 200-DMA, "
        f"{r.vs_short_pct:+.1f}% vs 20-DMA, breadth {r.breadth_up_pct:.0f}% up "
        f"(last {r.breadth_window}), VIX {vix}{flag}"
    )


def render_markdown(r: RegimeSummary, *, day: date) -> str:
    out = [
        f"# Market regime — {day}",
        "",
        "_Read-only. The tape the two-window autopsy showed matters more than the 200-DMA level "
        "alone: NIFTY was below its 200-DMA in BOTH the +₹16k and the −₹8k window — "
        "**breadth/slope** was what separated them. This flags when the LEVEL (vs 200-DMA) and "
        "the BREADTH (% up-days, vs 20-DMA) disagree, the signal a level-only gate would miss._",
        "",
    ]
    if not r.enough:
        out += [f"_Insufficient index history: {r.note}._", ""]
        return "\n".join(out) + "\n"

    vix = f"{r.vix:.1f}" if r.vix is not None else "—"
    out += [
        f"**{r.market_symbol}** ({r.note}):",
        "",
        "| metric | value |",
        "|---|--:|",
        f"| last close | {r.last_close:,.0f} |",
        f"| vs 200-DMA (level) | {r.vs_long_pct:+.1f}% |",
        f"| vs 20-DMA (trend) | {r.vs_short_pct:+.1f}% |",
        f"| breadth (last {r.breadth_window}) | {r.breadth_up_pct:.0f}% up-days |",
        f"| return (last {r.breadth_window}) | {r.short_return_pct:+.1f}% |",
        f"| VIX | {vix} |",
        "",
    ]
    level = "risk-ON (above 200-DMA)" if r.level_bullish else "risk-OFF (below 200-DMA)"
    breadth = "risk-ON (broad + above 20-DMA)" if r.breadth_bullish else "risk-OFF (weak breadth)"
    if r.disagree:
        out += [
            f"**⚠ LEVEL vs BREADTH DISAGREE.** The 200-DMA level says **{level}**; short-term "
            f"breadth says **{breadth}**. The autopsy showed breadth was the better guide — a "
            "level-only regime gate (MCE slice 4 as built) would misread this tape. Treat fresh "
            "longs with caution when breadth is the risk-OFF side.",
            "",
        ]
    else:
        out += [
            f"**Level and breadth agree: {level.split(' ')[0]}.** {level}; {breadth}.",
            "",
        ]
    return "\n".join(out) + "\n"
