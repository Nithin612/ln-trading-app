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
from datetime import date
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
    # ── A29 — costs that do NOT scale with turnover ─────────────────────────
    #: FLAT ₹ per DELIVERY SELL, per scrip, **irrespective of quantity** — the
    #: depository (CDSL) charge, levied when shares leave the demat account. This is the
    #: only charge here that is size-independent, which is precisely why it matters: a
    #: percentage cost is neutral to position size, a flat one is not. It falls hardest on
    #: SMALL positions — which is exactly the shape the notional cap produces today and
    #: exactly the ₹1 lakh / 1–2 position shape live trading will have. Omitting it
    #: under-costed the paper book in the direction that flatters an already-negative
    #: expectancy.
    dp_charge_per_sell: Decimal
    #: Minimum total charge per executed leg. **Zero by default, and that is not an
    #: oversight**: the Zerodha cash-equity schedule has no such floor, and inventing one
    #: would fabricate a cost rather than model one. It exists so a broker that DOES levy a
    #: minimum can be represented without touching any call site — the same reason the
    #: rates live in a schedule rather than inline.
    min_charge_per_leg: Decimal = Decimal("0")


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
    # Zerodha's published all-in DP charge (≈2025): ₹15.34 per scrip per debit, GST
    # INCLUSIVE — which is why it is added after the GST line rather than into its base.
    # Same provenance and the same caveat as every other rate here: a schedule figure held
    # in one editable place, not a derived quantity.
    dp_charge_per_sell=Decimal("15.34"),
)

# ── A23 — the effective-dated registry ──────────────────────────────────────
# The module docstring has claimed since Phase 8 that costs are "versioned by effective
# date", and the constant above carried a note that "a future effective-dated registry can
# replace this constant". This is that registry. Statutory Indian rates (STT above all)
# change mid-year, and a trade must be costed with the rates in force ON ITS OWN DATE —
# otherwise a record spanning a change is silently priced at today's rates.


@dataclass(frozen=True)
class DatedSchedule:
    """A schedule and the date it took effect."""

    effective_from: date
    schedule: FeeSchedule
    note: str


#: Ascending by `effective_from`. **To record a rate change, append an entry — never edit
#: an existing one**, exactly as with a migration: editing history silently re-prices every
#: trade already costed under the old rates.
#:
#: ⚠ There is ONE entry today, so `schedule_for` returns the same schedule for every date.
#: That is not a placeholder to be filled with guesses: we hold no researched history of
#: Indian statutory rate changes, and inventing effective dates would fabricate precision
#: rather than model it — the same error as inventing a per-trade cost floor. Its
#: `effective_from` is a COVERAGE FLOOR ("we model nothing earlier"), not a claim that
#: these rates began in 2000.
SCHEDULE_HISTORY: tuple[DatedSchedule, ...] = (
    DatedSchedule(
        effective_from=date(2000, 1, 1),
        schedule=ZERODHA_EQUITY,
        note="Zerodha NSE cash-equity schedule (≈2025), incl. the ₹15.34 DP charge (A29). "
        "Coverage floor, not a researched start date.",
    ),
)


def schedule_for(on: date) -> FeeSchedule:
    """The schedule in force on `on` — the latest entry whose `effective_from` ≤ `on`.

    Raises for a date before the registry's coverage rather than silently falling back to
    the earliest schedule. A cost we cannot source is unknown, and this project's repeated
    lesson is that unknown must be loud rather than read as a verified value.
    """
    match: FeeSchedule | None = None
    for entry in SCHEDULE_HISTORY:
        if entry.effective_from <= on:
            match = entry.schedule
        else:
            break
    if match is None:
        raise ValueError(
            f"no fee schedule covers {on.isoformat()} — the registry starts at "
            f"{SCHEDULE_HISTORY[0].effective_from.isoformat()}. Costing a trade with rates "
            "from outside their period would be a fabricated number, so this refuses "
            "rather than guessing."
        )
    return match


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
    dp_charge: Decimal
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
    on: date | None = None,
    schedule: FeeSchedule | None = None,
) -> ChargeBreakdown:
    """Charges for ONE executed leg. `side` in {BUY, SELL}; `product` in PRODUCTS.

    Components are kept at full precision; only the leg `total` is rounded to
    paise (matches how the round-trip total is stored).

    **A23 — pass `on`, the date this leg EXECUTED**, and the rates in force on that date
    are used. An explicit `schedule` overrides it (tests, and what-if costing). Passing
    neither falls back to the current schedule, which is correct for a fill happening now
    and wrong for anything historical — so historical callers should always pass `on`.
    """
    side = side.upper()
    if schedule is None:
        schedule = schedule_for(on) if on is not None else ZERODHA_EQUITY
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
    # A29 — the flat depository charge. DELIVERY SELL only: it is levied when shares leave
    # the demat account, so it has no intraday analogue and no buy-side analogue. Added
    # AFTER `gst` because the schedule figure is already GST-inclusive.
    #
    # ⚠ Applied to the SELL leg wherever it falls, which for a delivery SHORT means the
    # ENTRY. A cash-equity delivery short is not actually possible (you cannot deliver
    # stock you do not hold), so that combination is an artefact of the paper model rather
    # than a real trade; charging it consistently is closer to right than exempting it.
    dp = (
        schedule.dp_charge_per_sell
        if (product == "delivery" and side == "SELL")
        else Decimal("0")
    )
    total = brokerage + stt + exchange_txn + sebi + gst + stamp + dp
    total = max(total, schedule.min_charge_per_leg)
    return ChargeBreakdown(
        brokerage=brokerage,
        stt=stt,
        exchange_txn=exchange_txn,
        sebi=sebi,
        gst=gst,
        stamp_duty=stamp,
        dp_charge=dp,
        total=_paise(total),
    )


def roundtrip_charges(
    *,
    position_side: str,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: int,
    product: str,
    entry_on: date | None = None,
    exit_on: date | None = None,
    schedule: FeeSchedule | None = None,
) -> tuple[Decimal, dict[str, object]]:
    """Total charges for a full open→close round trip, plus a per-leg
    breakdown suitable for stashing in the closing order's audit payload.

    A LONG buys to enter and sells to exit; a SHORT is mirrored.

    **A23 — each leg is costed on ITS OWN date.** A position opened before a statutory rate
    change and closed after it really did pay two different schedules, and collapsing that
    to one is the error the registry exists to prevent. The breakdown records the effective
    date used per leg, so a cost can be re-derived from the record alone.
    """
    is_long = position_side.upper() == "LONG"
    entry_side = "BUY" if is_long else "SELL"
    exit_side = "SELL" if is_long else "BUY"
    entry_leg = leg_charges(
        side=entry_side, product=product, price=entry_price, qty=quantity,
        on=entry_on, schedule=schedule,
    )
    exit_leg = leg_charges(
        side=exit_side, product=product, price=exit_price, qty=quantity,
        on=exit_on, schedule=schedule,
    )
    total = _paise(entry_leg.total + exit_leg.total)
    breakdown: dict[str, object] = {
        "entry": {
            "side": entry_side,
            "priced_on": entry_on.isoformat() if entry_on else None,
            **entry_leg.as_dict(),
        },
        "exit": {
            "side": exit_side,
            "priced_on": exit_on.isoformat() if exit_on else None,
            **exit_leg.as_dict(),
        },
        "product": product,
    }
    return total, breakdown
