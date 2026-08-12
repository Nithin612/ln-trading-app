"""Tape-window excursion primitives (MFE/MAE) — the single source of truth.

Extracted from `daily_report` so both the daily report (per POSITION) and the
signal-outcome excursion recorder (per SIGNAL, Phase 6 slice 6.1) compute
max-favourable / max-adverse excursion identically, from the 1m tape.

Convention (unchanged from the original daily-report definition):
  - ``mfe_r`` is favourable R (≥ 0 once price ever moved in favour);
  - ``mae_r`` is the adverse extreme expressed as a *negative* favourable R
    (≤ 0), NOT a magnitude — so ``mae_r == -1.0`` means price traded a full R
    against the entry.

``side`` here is "LONG"/"SHORT"; callers holding BUY/SELL must map first.
Pure computation + a read-only bar loader; never feeds scoring/sizing/gating.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Ohlcv1m
from app.trading.trail_sl import compute_pnl

_Q2 = Decimal("0.01")
_Q3 = Decimal("0.001")


def _d(x: object) -> Decimal:
    """Decimal from anything money-shaped (str path — never through float)."""
    return Decimal(str(x))


@dataclass(frozen=True)
class Excursion:
    """Max favourable / adverse excursion over a tape window, with timing, in R
    (R = the trade's risk, |entry − sig_sl|)."""

    bars: int
    entry: Decimal
    risk: Decimal
    mfe_price: Decimal
    mfe_time: datetime
    mfe_r: Decimal
    mfe_pnl: Decimal
    mae_price: Decimal
    mae_time: datetime
    mae_r: Decimal
    mae_pnl: Decimal
    last_close: Decimal
    last_time: datetime
    reached_1r: bool


def tape_excursion(
    bars: list[tuple[datetime, Decimal, Decimal, Decimal]],
    *,
    side: str,
    entry: Decimal,
    risk: Decimal,
    quantity: int,
) -> Excursion | None:
    """Compute MFE/MAE + timing over ``bars`` (time, high, low, close).

    ``risk`` is R in price terms (|entry − sig_sl|); mfe_r/mae_r are excursions
    expressed in that R. Returns None on an empty tape.
    """
    if not bars:
        return None
    is_long = side.upper() == "LONG"
    qty = Decimal(quantity)

    mfe_price = bars[0][1] if is_long else bars[0][2]
    mfe_time = bars[0][0]
    mae_price = bars[0][2] if is_long else bars[0][1]
    mae_time = bars[0][0]

    for t, high, low, _close in bars:
        fav = high if is_long else low
        adv = low if is_long else high
        if (is_long and fav > mfe_price) or (not is_long and fav < mfe_price):
            mfe_price, mfe_time = fav, t
        if (is_long and adv < mae_price) or (not is_long and adv > mae_price):
            mae_price, mae_time = adv, t

    def _fav_r(price: Decimal) -> Decimal:
        move = (price - entry) if is_long else (entry - price)
        return (move / risk) if risk > 0 else Decimal(0)

    mfe_r = _fav_r(mfe_price)
    mae_r = _fav_r(mae_price)  # adverse extreme → negative favourable R
    return Excursion(
        bars=len(bars),
        entry=entry,
        risk=risk,
        mfe_price=mfe_price,
        mfe_time=mfe_time,
        mfe_r=mfe_r.quantize(_Q3),
        mfe_pnl=compute_pnl(
            side=side, entry=entry, exit_price=mfe_price, quantity=quantity
        ).quantize(_Q2),
        mae_price=mae_price,
        mae_time=mae_time,
        mae_r=mae_r.quantize(_Q3),
        mae_pnl=(qty * (mae_price - entry) if is_long else qty * (entry - mae_price)).quantize(_Q2),
        last_close=bars[-1][3],
        last_time=bars[-1][0],
        reached_1r=mfe_r >= 1,
    )


async def load_1m_bars(
    db: AsyncSession, stock_id: int, start: datetime, end: datetime
) -> list[tuple[datetime, Decimal, Decimal, Decimal]]:
    """Completed 1m bars (time, high, low, close) in [start, end], ascending.

    ``is_complete`` only — a forming candle never enters an excursion (no
    look-ahead / no repaint).
    """
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
    return [(r.time, _d(r.high), _d(r.low), _d(r.close)) for r in rows]
