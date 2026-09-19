"""Queue item 20 — capital-gains tax, and why it does NOT move break-even.

⛔⛔ **The correction that reframed this item (BT22, round 11).** The queue originally carried
tax as a cost to add to the break-even stack. That is wrong, and the reason is worth stating
once precisely: **tax is levied on PROFIT.** At break-even the profit is zero, so the tax is
zero, so **break-even does not move.** What tax does is raise every **TARGET** — the gross
return required to deliver a given net return. Adding it to the cost stack would have made
every break-even figure in the programme too pessimistic, including item 5's.

⚠ **So nothing here belongs in a bps cost model.** `fees.py` prices turnover; this prices
outcome. They compose only at the end, on a realised P&L, and never inside a break-even.

## What is modelled

Indian equities, STT-paid, on-exchange:

- **Short-term** (holding ≤ 12 months) — §111A. **15% until 2024-07-22, 20% from 2024-07-23.**
- **Long-term** (> 12 months) — §112A. **10% above a ₹1,00,000 exemption until 2024-07-22;
  12.5% above ₹1,25,000 from 2024-07-23.**
- **Health & education cess** of 4% on the tax itself, throughout.

⭐⭐ **THE RATE CHANGE SITS INSIDE OUR TEST BLOCK.** The block runs 2023-07-03 → today and the
Budget-2024 change took effect **2024-07-23**, so **both regimes are in the window**. A
single-rate model would be wrong for roughly the first year of it — which is exactly why A23
introduced effective-dated schedules, and why this module copies that pattern rather than
holding a constant.

⛔ **Intraday is NOT modelled and must not be guessed.** Intraday equity is *speculative
business income*, taxed at the individual's slab rate together with all other income — it has
no flat rate to encode. `SLAB_UNKNOWN` is returned so a caller must supply one deliberately;
inventing a number here would fabricate precision, the same error as inventing a per-trade
cost floor (`min_charge_per_leg`, deliberately 0).

⚠ **Not modelled, deliberately:** surcharge (income-dependent), set-off of losses against
gains, carry-forward, the ₹1.25L exemption being ANNUAL and shared across all LTCG rather than
per-trade. This module prices ONE disposal in isolation; a portfolio-level tax position is a
different question and belongs with standing concession 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

#: Returned by the rate lookup when the product has no flat statutory rate.
SLAB_UNKNOWN = "slab_unknown"

_PAISE = Decimal("0.01")


@dataclass(frozen=True)
class TaxSchedule:
    """Statutory equity capital-gains rates in force over a period."""

    short_term_rate: Decimal
    long_term_rate: Decimal
    long_term_exemption: Decimal
    cess_rate: Decimal


@dataclass(frozen=True)
class DatedTaxSchedule:
    effective_from: date
    schedule: TaxSchedule
    note: str


#: Ascending by `effective_from`. **Append to record a change — never edit an entry**, for the
#: same reason `fees.SCHEDULE_HISTORY` says so: editing history silently re-prices every
#: outcome already computed under the old rates.
TAX_HISTORY: tuple[DatedTaxSchedule, ...] = (
    DatedTaxSchedule(
        effective_from=date(2018, 4, 1),
        schedule=TaxSchedule(
            short_term_rate=Decimal("0.15"),
            long_term_rate=Decimal("0.10"),
            long_term_exemption=Decimal("100000"),
            cess_rate=Decimal("0.04"),
        ),
        note="§111A 15% / §112A 10% above ₹1L. Coverage floor: LTCG on equity was "
        "reintroduced by Finance Act 2018 effective 2018-04-01.",
    ),
    DatedTaxSchedule(
        effective_from=date(2024, 7, 23),
        schedule=TaxSchedule(
            short_term_rate=Decimal("0.20"),
            long_term_rate=Decimal("0.125"),
            long_term_exemption=Decimal("125000"),
            cess_rate=Decimal("0.04"),
        ),
        note="Budget 2024: §111A 15%→20%, §112A 10%→12.5%, exemption ₹1L→₹1.25L. "
        "⭐ This date falls INSIDE the 2023-07-03→ test block.",
    ),
)

#: The long-term boundary for listed equity: held for MORE than 12 months.
LONG_TERM_DAYS = 365


def schedule_for(on: date) -> TaxSchedule:
    """The schedule in force on `on`. Raises before the registry's coverage floor.

    ⚠ Raises rather than falling back to the earliest entry, mirroring `fees.schedule_for`:
    a rate we cannot source is unknown, and unknown must be loud.
    """
    match: TaxSchedule | None = None
    for entry in TAX_HISTORY:
        if entry.effective_from <= on:
            match = entry.schedule
        else:
            break
    if match is None:
        raise ValueError(
            f"no tax schedule covers {on} — the registry starts "
            f"{TAX_HISTORY[0].effective_from}. Append an entry rather than guessing."
        )
    return match


def holding_class(entry_on: date, exit_on: date, product: str) -> str:
    """`"intraday"`, `"short_term"` or `"long_term"`.

    ⚠ Intraday is decided by the PRODUCT, not the dates: a delivery trade opened and closed
    the same session is still a capital gain, whereas an MIS trade is speculative business
    income however long it is held (it cannot be held overnight at all).
    """
    if product == "intraday":
        return "intraday"
    if (exit_on - entry_on).days > LONG_TERM_DAYS:
        return "long_term"
    return "short_term"


def capital_gains_tax(
    gain: Decimal,
    *,
    entry_on: date,
    exit_on: date,
    product: str = "delivery",
    long_term_exemption_used: Decimal = Decimal("0"),
) -> Decimal | str:
    """Tax on ONE disposal, or `SLAB_UNKNOWN` for intraday.

    ⭐ **Zero on a loss and zero at break-even** — which is the whole point of item 20's
    correction. A caller adding this to a cost stack would be double-counting nothing at the
    only place a cost stack matters.

    `long_term_exemption_used` lets a caller thread the ANNUAL exemption across disposals;
    left at zero, each disposal is priced as though it had the whole allowance, which
    understates tax on the second and later long-term disposals of a year.
    """
    if gain <= 0:
        return Decimal("0.00")
    kind = holding_class(entry_on, exit_on, product)
    if kind == "intraday":
        return SLAB_UNKNOWN

    sched = schedule_for(exit_on)
    if kind == "long_term":
        remaining = max(Decimal("0"), sched.long_term_exemption - long_term_exemption_used)
        taxable = max(Decimal("0"), gain - remaining)
        base = taxable * sched.long_term_rate
    else:
        base = gain * sched.short_term_rate

    return (base * (Decimal("1") + sched.cess_rate)).quantize(_PAISE, rounding=ROUND_HALF_UP)


def pretax_target_for(
    after_tax_target: Decimal,
    *,
    entry_on: date,
    exit_on: date,
    product: str = "delivery",
) -> Decimal | str:
    """The GROSS gain needed to net `after_tax_target`.

    ⭐⭐ **This is the direction item 20 is actually about.** Tax does not move break-even; it
    moves the target. A ₹10,000 net on a short-term delivery trade closed after the 2024
    change needs ₹13,020 gross, not ₹10,000 — and nothing in the system said so.

    ⚠ Long-term is solved on the taxable excess, so the exemption is applied first; below the
    exemption the pre-tax target equals the after-tax one.
    """
    if after_tax_target <= 0:
        return after_tax_target
    kind = holding_class(entry_on, exit_on, product)
    if kind == "intraday":
        return SLAB_UNKNOWN

    sched = schedule_for(exit_on)
    if kind == "long_term":
        if after_tax_target <= sched.long_term_exemption:
            return after_tax_target.quantize(_PAISE, rounding=ROUND_HALF_UP)
        excess = after_tax_target - sched.long_term_exemption
        effective = sched.long_term_rate * (Decimal("1") + sched.cess_rate)
        gross_excess = excess / (Decimal("1") - effective)
        return (sched.long_term_exemption + gross_excess).quantize(
            _PAISE, rounding=ROUND_HALF_UP
        )

    effective = sched.short_term_rate * (Decimal("1") + sched.cess_rate)
    return (after_tax_target / (Decimal("1") - effective)).quantize(
        _PAISE, rounding=ROUND_HALF_UP
    )
