"""Profit-lock shadow comparator — replays candidate exit policies over the
stored 1-minute tape of a position and reports where each WOULD have exited.

Shadow-only: it executes nothing and touches no real orders. It exists to
gather evidence — does the Layered Ratchet Stop keep more of the peak profit
than the current trail ladder, without cutting genuine trends short? — before
the mechanism is ever allowed to drive live stops.

Replay is offline from committed 1m candles (not the 60s live monitor), so it
can look PAST the real exit to the end of the holding window and capture the
"would have held longer" benefit that motivated the whole exercise. Method is
the conservative one used in the manual LENSKART analysis: for each bar, test
the stop already in force against the adverse extreme FIRST, then update the
peak from the favourable extreme, then recompute the stop for the next bar —
no intra-bar look-ahead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Ohlcv1m
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.trading.atr import atr_timeframe_for, latest_atr
from app.trading.fees import product_for_classification, roundtrip_charges
from app.trading.profit_lock import RatchetParams, layered_ratchet_stop, params_for
from app.trading.trail_sl import advance_trail, compute_pnl, is_sl_hit


@dataclass
class Bar:
    time: datetime
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass
class PolicyResult:
    policy: str
    exit_price: Decimal | None
    exit_time: datetime | None
    exit_gross: Decimal | None
    exit_net: Decimal | None
    still_open: bool                 # never stopped inside the window (censored)
    capture_pct: float | None        # exit_net / peak_gross


@dataclass
class ShadowComparison:
    position_id: str
    symbol: str
    side: str
    quantity: int
    entry: Decimal
    original_sl: Decimal
    classification: str
    bars: int
    peak_price: Decimal | None
    peak_gross: Decimal | None       # max favourable excursion over the window
    actual_exit_price: Decimal | None
    actual_net: Decimal | None       # realised (closed) — net of costs
    actual_capture_pct: float | None
    policies: list[PolicyResult]
    # True when the recorded exit price is BETTER than anything that really
    # traded in the window — i.e. the trade closed on a stale/pre-open price
    # (the fixed monitor bug). The realised P&L is then untrustworthy and no
    # capture % is computed against it.
    actual_exit_off_tape: bool = False
    note: str | None = None


# A step returns the new stop given (peak_price, current_stop). Layered policies
# are stateless; the ladder keeps its state in a closure.
_Step = Callable[[Decimal, Decimal], Decimal]


def _giveback_only(fraction: str) -> RatchetParams:
    """A pure fixed-giveback policy (no ATR chandelier) — a reference point."""
    f = Decimal(fraction)
    return RatchetParams(
        arm_r=Decimal("1.0"), atr_k=Decimal("0"), giveback_early=f, giveback_late=f
    )


def _layered_step(
    side: str, entry: Decimal, original_sl: Decimal, atr: Decimal | None, params: RatchetParams
) -> _Step:
    def step(peak_price: Decimal, current_stop: Decimal) -> Decimal:
        return layered_ratchet_stop(
            side=side,
            entry=entry,
            original_sl=original_sl,
            peak_price=peak_price,
            atr=atr,
            params=params,
            current_stop=current_stop,
        )

    return step


def _ladder_step(side: str, entry: Decimal, original_sl: Decimal) -> _Step:
    state = {"s": "none"}

    def step(peak_price: Decimal, current_stop: Decimal) -> Decimal:
        r = advance_trail(
            side=side,
            entry=entry,
            original_sl=original_sl,
            current_sl=current_stop,
            current_price=peak_price,  # best price drives the ladder's advancement
            current_state=state["s"],
        )
        state["s"] = r.new_state
        return r.new_sl

    return step


def _replay(
    bars: Sequence[Bar], *, side: str, entry: Decimal, original_sl: Decimal, step: _Step
) -> tuple[Decimal | None, datetime | None, bool]:
    """Return (exit_price, exit_time, still_open). still_open means the stop was
    never hit within the window."""
    is_long = side.upper() == "LONG"
    stop = original_sl
    peak = entry
    for bar in bars:
        adverse = bar.low if is_long else bar.high
        if is_sl_hit(side=side, current_price=adverse, current_sl=stop):
            return stop, bar.time, False
        fav = bar.high if is_long else bar.low
        if (is_long and fav > peak) or (not is_long and fav < peak):
            peak = fav
        stop = step(peak, stop)
    return None, None, True


def _capture(net: Decimal | None, peak_gross: Decimal | None) -> float | None:
    if net is None or peak_gross is None or peak_gross <= 0:
        return None
    return float(net / peak_gross)


async def _load_bars(db: AsyncSession, stock_id: int, start: datetime, end: datetime) -> list[Bar]:
    rows = (
        await db.execute(
            select(Ohlcv1m.time, Ohlcv1m.high, Ohlcv1m.low, Ohlcv1m.close)
            .where(
                Ohlcv1m.stock_id == stock_id,
                Ohlcv1m.is_complete.is_(True),
                Ohlcv1m.time >= start,
                Ohlcv1m.time <= end,
            )
            .order_by(Ohlcv1m.time.asc())
        )
    ).all()
    return [
        Bar(
            time=r.time,
            high=Decimal(str(r.high)),
            low=Decimal(str(r.low)),
            close=Decimal(str(r.close)),
        )
        for r in rows
    ]


async def compare_position(
    db: AsyncSession, position: Position, *, now: datetime
) -> ShadowComparison:
    """Replay the exit policies over one position's 1m tape."""
    stock = await db.get(Stock, position.stock_id)
    symbol = stock.symbol if stock is not None else ""

    classification = "swing"
    original_sl = position.current_sl
    if position.signal_id is not None:
        sig = await db.get(Signal, position.signal_id)
        if sig is not None:
            classification = sig.classification
            original_sl = sig.stop_loss

    entry = Decimal(str(position.avg_entry_price))
    side = position.side
    qty = position.quantity
    product = product_for_classification(classification)

    base = ShadowComparison(
        position_id=position.id,
        symbol=symbol,
        side=side,
        quantity=qty,
        entry=entry,
        original_sl=Decimal(str(original_sl)) if original_sl is not None else entry,
        classification=classification,
        bars=0,
        peak_price=None,
        peak_gross=None,
        actual_exit_price=(
            Decimal(str(position.exit_price)) if position.exit_price is not None else None
        ),
        actual_net=(
            position.realized_pnl if position.closed_at is not None else position.unrealized_pnl
        ),
        actual_capture_pct=None,
        policies=[],
    )

    if original_sl is None:
        base.note = "no stop-loss on the signal — cannot replay"
        return base

    end = position.closed_at or now
    bars = await _load_bars(db, position.stock_id, position.opened_at, end)
    base.bars = len(bars)
    if len(bars) < 2:
        base.note = "insufficient 1m candle data for the holding window"
        return base

    orig_sl = Decimal(str(original_sl))
    is_long = side.upper() == "LONG"

    # MFE over the window (gross peak profit), from the real tape.
    true_high = max(b.high for b in bars)
    true_low = min(b.low for b in bars)
    peak_price = true_high if is_long else true_low
    peak_gross = compute_pnl(side=side, entry=entry, exit_price=peak_price, quantity=qty)
    base.peak_price = peak_price
    base.peak_gross = peak_gross

    # If the recorded exit is BETTER than anything that really traded (a short
    # closed below the true low, or a long above the true high), it closed on a
    # stale/pre-open price — the fixed monitor bug. The realised P&L is then
    # fictional (Peak < realised), so flag it and don't compute a capture %.
    exit_px = base.actual_exit_price
    if exit_px is not None and (
        (is_long and exit_px > true_high) or (not is_long and exit_px < true_low)
    ):
        base.actual_exit_off_tape = True
        base.note = "exit off-tape (stale/pre-open close) — realised P&L unreliable"
    else:
        base.actual_capture_pct = _capture(base.actual_net, peak_gross)

    atr = await latest_atr(
        db,
        position.stock_id,
        timeframe=atr_timeframe_for(classification),
        before=position.opened_at,
    )

    policies: dict[str, _Step] = {
        "ladder": _ladder_step(side, entry, orig_sl),
        "layered": _layered_step(side, entry, orig_sl, atr, params_for(classification)),
        "giveback_33": _layered_step(side, entry, orig_sl, None, _giveback_only("0.33")),
    }

    last_close = bars[-1].close
    for name, step in policies.items():
        exit_price, exit_time, still_open = _replay(
            bars, side=side, entry=entry, original_sl=orig_sl, step=step
        )
        # Censor an un-stopped policy at the last close (its future is unknown).
        eff_price = exit_price if exit_price is not None else last_close
        gross = compute_pnl(side=side, entry=entry, exit_price=eff_price, quantity=qty)
        charges, _ = roundtrip_charges(
            position_side=side,
            entry_price=entry,
            exit_price=eff_price,
            quantity=qty,
            product=product,
        )
        net = gross - charges
        base.policies.append(
            PolicyResult(
                policy=name,
                exit_price=eff_price,
                exit_time=exit_time,
                exit_gross=gross,
                exit_net=net,
                still_open=still_open,
                capture_pct=_capture(net, peak_gross),
            )
        )

    return base
