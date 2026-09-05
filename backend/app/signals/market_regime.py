"""Market-regime eligibility overlay — MCE slice 4 (the top of the top-down funnel).

Above sector-RS (which asks "is the stock's sector/index leading?") sits the broadest
top-down filter: **is the market itself risk-on or risk-off?** A fresh long into a market
that is below its 200-DMA is fighting the tape; a fresh short into a market above its
200-DMA is the mirror. This overlay reads the broad-market index (NIFTY 50) trend and the
India-VIX level and decides eligibility for a signal's side.

Same shape as `sector_rs` / `circuit_guard` / `regime_guard` / `entry_quality`: **pure**
(no I/O), **moded** (off / shadow / active), **fail-open**. Frozen confluence engine
untouched (a downstream overlay).

Two dimensions:
  - **200-DMA trend (the gate).** Market below its `dma_period`-session SMA ⇒ down-trend.
    A LONG is flagged when the market is below (× the buffer); a SHORT when it is above.
    This is the dimension that can go active — it is §8-validatable on our 3y of daily
    history.
  - **India VIX (informational companion, NOT a gate).** The latest VIX and whether it is
    elevated are reported for context + the shadow sidecar; VIX never drives the block.

    ⚠ **The old note here — "our VIX history is too shallow (~weeks)" — was STALE.**
    `india_vix_daily` holds **784 sessions, 2023-07-03 → 2026-09-04**; the backfill has
    happened, the same way the index backfill had (corrected 2026-09-02).

    **H3 — the threshold is a trailing PERCENTILE, not an absolute.** A fixed `20` is a
    US-derived number and it does not describe this market: India VIX has a median of
    **13.35** over those 784 sessions and exceeds 20 on only **5.1%** of them, so "20 =
    elevated" is really the **94.8th percentile** — an extreme, not the "somewhat nervous"
    marker it reads as. The 80th percentile sits at **15.73**. A percentile is
    self-calibrating and distribution-free: it keeps meaning the same thing as the VIX
    regime drifts, and it needs no view about what number is high in India.

    The absolute threshold remains the fallback when history is too shallow to rank
    against, and `vix_basis` always says which one produced the flag — the two must never
    be confused for each other.

**Fail-open:** fewer than `dma_period` market closes (history not deep enough) ⇒ eligible,
never suppress on uncertainty. The market close series must be aligned to the signal's own
decision time by the caller (no look-ahead) — same contract as `sector_rs`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

_Q = Decimal("0.0001")
_HUNDRED = Decimal(100)


def _pos_side(side: str) -> str:
    """BUY/LONG → LONG, else SHORT. Mirrors the sibling overlays."""
    return "LONG" if side.upper() in ("BUY", "LONG") else "SHORT"


@dataclass(frozen=True)
class RegimeVerdict:
    """The overlay's read on one signal — stamped on the order's
    ``broker_payload["market_regime"]`` so the shadow report can aggregate what it WOULD
    suppress and any decision is reconstructable. Percents/prices are ``Decimal`` (a float
    round-trip through JSON would lose exactness)."""

    blocked: bool
    has_data: bool  # False ⇒ history shorter than dma_period; blocked is False (fail-open)
    side: str  # LONG | SHORT
    market_symbol: str
    dma_period: int
    market_close: Decimal | None = None  # latest broad-market close (as-of the signal)
    dma: Decimal | None = None  # the dma_period-session SMA
    gap_pct: Decimal | None = None  # (market_close / dma − 1) × 100; <0 ⇒ below the DMA
    vix: Decimal | None = None  # latest India VIX (informational)
    vix_threshold: Decimal | None = None  # the ABSOLUTE fallback threshold
    vix_elevated: bool | None = None  # elevated by `vix_basis` (informational, never blocks)
    #: Where the current VIX sits in its own trailing history, 0–1. None when there is not
    #: enough history to rank against.
    vix_percentile: Decimal | None = None
    #: "percentile" | "absolute" | None — which basis produced `vix_elevated`. Reported so
    #: the two can never be mistaken for one another (H3/A24).
    vix_basis: str | None = None
    reasons: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        def s(v: Decimal | None) -> str | None:
            return str(v.quantize(_Q)) if v is not None else None

        return {
            "blocked": self.blocked,
            "has_data": self.has_data,
            "side": self.side,
            "market_symbol": self.market_symbol,
            "dma_period": self.dma_period,
            "market_close": s(self.market_close),
            "dma": s(self.dma),
            "gap_pct": s(self.gap_pct),
            "vix": s(self.vix),
            "vix_threshold": s(self.vix_threshold),  # quantized like the other Decimals
            "vix_elevated": self.vix_elevated,
            "vix_percentile": s(self.vix_percentile),
            "vix_basis": self.vix_basis,
            "reasons": list(self.reasons),
        }


#: Sessions of VIX history needed before a percentile means anything. Below this the rank
#: is a handful of atoms and the absolute fallback is more honest.
MIN_VIX_HISTORY = 250


def vix_standing(
    vix: Decimal | None,
    history: Sequence[Decimal] | None,
    *,
    percentile_threshold: Decimal,
    absolute_threshold: Decimal,
) -> tuple[bool | None, Decimal | None, str | None]:
    """`(elevated, percentile, basis)` for the current VIX — H3.

    Prefers the trailing percentile, because a fixed level is a claim about what is high in
    a market and we have no basis for one (the inherited `20` turns out to be India's
    94.8th percentile). Falls back to the absolute when history is too shallow to rank
    against, and always names the basis, so a `True` from one is never read as a `True`
    from the other.
    """
    if vix is None:
        return None, None, None
    if history is not None and len(history) >= MIN_VIX_HISTORY:
        ranked = sorted(history)
        # Fraction of the history strictly below the current value — the standard
        # "percentile rank", and the natural reading of "VIX is high for this market".
        below = sum(1 for h in ranked if h < vix)
        pct = Decimal(below) / Decimal(len(ranked))
        return pct >= percentile_threshold, pct, "percentile"
    return vix > absolute_threshold, None, "absolute"


def evaluate(
    *,
    side: str,
    market_closes: Sequence[Decimal],
    dma_period: int = 200,
    buffer_pct: Decimal = Decimal(0),
    vix: Decimal | None = None,
    vix_threshold: Decimal = Decimal(20),
    vix_history: Sequence[Decimal] | None = None,
    vix_percentile_threshold: Decimal = Decimal("0.80"),
    market_symbol: str = "NIFTY50",
) -> RegimeVerdict:
    """Judge a signal's side against the broad-market 200-DMA trend.

    LONG is flagged when the latest market close is below its ``dma_period`` SMA (× the
    lower buffer); SHORT when it is above (× the upper buffer). VIX is reported but never
    blocks. Fail-open (un-blocked, ``has_data`` False) when there are fewer than
    ``dma_period`` closes."""
    pos_side = _pos_side(side)
    elevated, vix_pct, basis = vix_standing(
        vix,
        vix_history,
        percentile_threshold=vix_percentile_threshold,
        absolute_threshold=vix_threshold,
    )
    base = RegimeVerdict(
        blocked=False,
        has_data=False,
        side=pos_side,
        market_symbol=market_symbol,
        dma_period=dma_period,
        vix=vix,
        vix_threshold=vix_threshold,
        vix_elevated=elevated,
        vix_percentile=vix_pct,
        vix_basis=basis,
    )
    if len(market_closes) < dma_period or dma_period <= 0:
        return RegimeVerdict(
            **{**base.__dict__, "reasons": ["market history shorter than dma_period"]}
        )

    window = market_closes[-dma_period:]
    dma = sum(window, Decimal(0)) / Decimal(dma_period)
    market_close = market_closes[-1]
    if dma <= 0:
        return RegimeVerdict(**{**base.__dict__, "reasons": ["degenerate DMA"]})

    gap_pct = (market_close / dma - Decimal(1)) * _HUNDRED
    lower = dma * (Decimal(1) - buffer_pct / _HUNDRED)
    upper = dma * (Decimal(1) + buffer_pct / _HUNDRED)

    reasons: list[str] = []
    if pos_side == "LONG":
        blocked = market_close < lower
        if blocked:
            reasons.append(
                f"LONG but {market_symbol} {market_close} is below its {dma_period}-DMA "
                f"{dma.quantize(_Q)} ({gap_pct.quantize(_Q)}%) — market down-trend, risk-off "
                "for longs"
            )
    else:
        blocked = market_close > upper
        if blocked:
            reasons.append(
                f"SHORT but {market_symbol} {market_close} is above its {dma_period}-DMA "
                f"{dma.quantize(_Q)} ({gap_pct.quantize(_Q)}%) — market up-trend, risk-off "
                "for shorts"
            )

    return RegimeVerdict(
        blocked=blocked,
        has_data=True,
        side=pos_side,
        market_symbol=market_symbol,
        dma_period=dma_period,
        market_close=market_close,
        dma=dma,
        gap_pct=gap_pct,
        vix=vix,
        vix_threshold=vix_threshold,
        vix_elevated=elevated,
        vix_percentile=vix_pct,
        vix_basis=basis,
        reasons=reasons,
    )


def order_block_reason(verdict: RegimeVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order, or None to allow it. Only ACTIVE blocks; in
    off/shadow this is a no-op. VIX never blocks (informational only)."""
    if mode != "active" or not verdict.blocked:
        return None
    detail = "; ".join(verdict.reasons) if verdict.reasons else "market regime against the side"
    return f"Signal fails the market-regime overlay: {detail}"
