"""Position sizing and stop-loss/take-profit placement.

Implements SIGNAL_ENGINE.md §6 exactly.
All prices are Decimal to avoid float rounding.
"""

from decimal import ROUND_DOWN, Decimal


def compute_quantity(
    capital: Decimal,
    risk_pct: Decimal,
    entry: Decimal,
    stop_loss: Decimal,
) -> int:
    """Return suggested share quantity given capital and max risk %.

    Formula: floor(capital * risk_pct/100 / |entry - stop_loss|)
    Raises ValueError if stop_loss == entry.
    """
    if entry == stop_loss:
        raise ValueError("Stop loss must differ from entry price")
    risk_amount = capital * (risk_pct / Decimal("100"))
    risk_per_share = abs(entry - stop_loss)
    qty = (risk_amount / risk_per_share).to_integral_value(rounding=ROUND_DOWN)
    return max(int(qty), 0)


def _pct(price: Decimal, pct: Decimal) -> Decimal:
    return (price * pct / Decimal("100")).quantize(Decimal("0.0001"))


def compute_levels(  # noqa: C901
    direction: str,
    classification: str,
    entry: Decimal,
    swing_low: Decimal | None = None,
    swing_high: Decimal | None = None,
    atr_pct: Decimal | None = None,
    ema20_daily: Decimal | None = None,
) -> tuple[Decimal, Decimal] | None:
    """Return (stop_loss, take_profit) or None if SL violates the max-SL rule.

    SL placement rules per SIGNAL_ENGINE.md §6.
    """
    if classification == "scalp":
        sl_pct = Decimal("0.30")
        max_sl_pct = Decimal("0.50")
        if direction == "BUY":
            sl = entry - _pct(entry, sl_pct)
            tp = entry + _pct(entry, Decimal("0.45"))  # 1:1.5 RR
        else:
            sl = entry + _pct(entry, sl_pct)
            tp = entry - _pct(entry, Decimal("0.45"))

    elif classification == "intraday":
        max_sl_pct = Decimal("0.50")
        if direction == "BUY":
            natural_sl = (
                swing_low if swing_low is not None
                else entry - _pct(entry, Decimal("0.30"))
            )
            sl = natural_sl
            tp = entry + (entry - sl) * Decimal("2")  # 1:2 RR
        else:
            natural_sl = (
                swing_high if swing_high is not None
                else entry + _pct(entry, Decimal("0.30"))
            )
            sl = natural_sl
            tp = entry - (sl - entry) * Decimal("2")

    elif classification == "swing":
        max_sl_pct = Decimal("8.00")
        if direction == "BUY":
            natural_sl = swing_low if swing_low is not None else entry - _pct(entry, Decimal("2"))
            sl = natural_sl
            tp = entry + _pct(entry, Decimal("6"))  # flat 6% RRBO target
        else:
            natural_sl = swing_high if swing_high is not None else entry + _pct(entry, Decimal("2"))
            sl = natural_sl
            tp = entry - _pct(entry, Decimal("6"))

    elif classification == "positional":
        max_sl_pct = Decimal("15.00")  # trailing; no hard cap
        if direction == "BUY":
            sl = ema20_daily if ema20_daily is not None else entry - _pct(entry, Decimal("5"))
            tp = entry + _pct(entry, Decimal("15"))  # minimum 15%
        else:
            sl = ema20_daily if ema20_daily is not None else entry + _pct(entry, Decimal("5"))
            tp = entry - _pct(entry, Decimal("15"))
    else:
        raise ValueError(f"Unknown classification: {classification}")

    # Validate SL does not exceed maximum allowed
    if classification != "positional":
        sl_distance_pct = abs(entry - sl) / entry * Decimal("100")
        if sl_distance_pct > max_sl_pct:
            return None  # signal rejected per spec

    return sl, tp
