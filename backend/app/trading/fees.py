"""Trading cost model — Indian cash-equity (Zerodha schedule), configurable.

Applied to paper fills so realized P&L is NET of costs. A paper record that
ignores brokerage/STT/GST overstates profitability and would falsely qualify
the account for live trading — defeating the 30-day paper gate's entire
purpose (trading-domain rule #6). See docs/paper_broker_execution_design
notes §19/§22: costs are first-class, versioned by effective date, never
hard-coded inside execution logic.

Scope: cash equity only (delivery + intraday). F&O charges are Phase 4.
Rates are the Zerodha equity schedule (≈2025) held in ONE editable place
(`ZERODHA_EQUITY`); behavioural toggles (`paper_costs_enabled`,
`paper_slippage_bps`) live in settings. All money math is Decimal — never
float (trading-domain money rule).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

_PAISE = Decimal("0.01")
_CRORE = Decimal("10000000")  # 1 crore, for SEBI ₹/cr turnover charge


def _paise(x: Decimal) -> Decimal:
    return x.quantize(_PAISE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeSchedule:
    """A versionable cash-equity charge schedule. Percentages are WHOLE
    percents of turnover (0.1 == 0.1%); `sebi_per_cr` is ₹ per crore of
    turnover; `intraday_brokerage_cap` is ₹ per executed order."""

    # Delivery (CNC) — held overnight
    delivery_brokerage_pct: Decimal
    delivery_stt_pct: Decimal      # both legs
    delivery_stamp_pct: Decimal    # BUY leg only
    # Intraday (MIS)
    intraday_brokerage_pct: Decimal
    intraday_brokerage_cap: Decimal   # ₹ per order
    intraday_stt_pct: Decimal      # SELL leg only
    intraday_stamp_pct: Decimal    # BUY leg only
    # Common to both products
    exchange_txn_pct: Decimal      # both legs (NSE equity)
    sebi_per_cr: Decimal           # ₹ per crore, both legs
    gst_pct: Decimal               # on (brokerage + exchange_txn + sebi)


# Zerodha NSE cash-equity schedule (≈2025). Edit here to adjust rates; a
# future effective-dated registry can replace this constant without
# touching call sites.
ZERODHA_EQUITY = FeeSchedule(
    delivery_brokerage_pct=Decimal("0"),
    delivery_stt_pct=Decimal("0.1"),
    delivery_stamp_pct=Decimal("0.015"),
    intraday_brokerage_pct=Decimal("0.03"),
    intraday_brokerage_cap=Decimal("20"),
    intraday_stt_pct=Decimal("0.025"),
    intraday_stamp_pct=Decimal("0.003"),
    exchange_txn_pct=Decimal("0.00297"),
    sebi_per_cr=Decimal("10"),
    gst_pct=Decimal("18"),
)

PRODUCTS = ("delivery", "intraday")


def product_for_classification(classification: str) -> str:
    """Map a signal classification to a settlement product.

    scalp/intraday are squared off same session → intraday (MIS) charges;
    swing/positional are held overnight → delivery (CNC) charges.
    """
    return "intraday" if classification in ("scalp", "intraday") else "delivery"


@dataclass(frozen=True)
class ChargeBreakdown:
    brokerage: Decimal
    stt: Decimal
    exchange_txn: Decimal
    sebi: Decimal
    gst: Decimal
    stamp_duty: Decimal
    total: Decimal

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


def _pct(turnover: Decimal, whole_pct: Decimal) -> Decimal:
    return turnover * whole_pct / Decimal("100")


def leg_charges(
    *,
    side: str,
    product: str,
    price: Decimal,
    qty: int,
    schedule: FeeSchedule = ZERODHA_EQUITY,
) -> ChargeBreakdown:
    """Charges for ONE executed leg. `side` in {BUY, SELL}; `product` in PRODUCTS.

    Components are kept at full precision; only the leg `total` is rounded to
    paise (matches how the round-trip total is stored).
    """
    side = side.upper()
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {product!r}")
    turnover = price * Decimal(qty)

    if product == "delivery":
        brokerage = Decimal("0")
        stt = _pct(turnover, schedule.delivery_stt_pct)  # both legs
        stamp = _pct(turnover, schedule.delivery_stamp_pct) if side == "BUY" else Decimal("0")
    else:  # intraday
        brokerage = min(
            _pct(turnover, schedule.intraday_brokerage_pct), schedule.intraday_brokerage_cap
        )
        stt = _pct(turnover, schedule.intraday_stt_pct) if side == "SELL" else Decimal("0")
        stamp = _pct(turnover, schedule.intraday_stamp_pct) if side == "BUY" else Decimal("0")

    exchange_txn = _pct(turnover, schedule.exchange_txn_pct)
    sebi = turnover * schedule.sebi_per_cr / _CRORE
    gst = _pct(brokerage + exchange_txn + sebi, schedule.gst_pct)
    total = brokerage + stt + exchange_txn + sebi + gst + stamp
    return ChargeBreakdown(
        brokerage=brokerage,
        stt=stt,
        exchange_txn=exchange_txn,
        sebi=sebi,
        gst=gst,
        stamp_duty=stamp,
        total=_paise(total),
    )


def roundtrip_charges(
    *,
    position_side: str,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: int,
    product: str,
    schedule: FeeSchedule = ZERODHA_EQUITY,
) -> tuple[Decimal, dict[str, object]]:
    """Total charges for a full open→close round trip, plus a per-leg
    breakdown suitable for stashing in the closing order's audit payload.

    A LONG buys to enter and sells to exit; a SHORT is mirrored.
    """
    is_long = position_side.upper() == "LONG"
    entry_side = "BUY" if is_long else "SELL"
    exit_side = "SELL" if is_long else "BUY"
    entry_leg = leg_charges(
        side=entry_side, product=product, price=entry_price, qty=quantity, schedule=schedule
    )
    exit_leg = leg_charges(
        side=exit_side, product=product, price=exit_price, qty=quantity, schedule=schedule
    )
    total = _paise(entry_leg.total + exit_leg.total)
    breakdown: dict[str, object] = {
        "entry": {"side": entry_side, **entry_leg.as_dict()},
        "exit": {"side": exit_side, **exit_leg.as_dict()},
        "product": product,
    }
    return total, breakdown
