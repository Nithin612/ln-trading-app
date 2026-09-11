"""The exchange tick grid, as a DATED PRICE-BAND SCHEDULE rather than one constant.

⛔ **The bug this replaces.** `paper_tick_size` was a single global `0.05`, price- and
date-independent, and `paper_broker._round_tick` snapped every simulated fill and every
mark to it — always adversely, which is the correct contract. But ₹0.05 has not been the
grid for cheap names since mid-2024. On a ₹39 share the expected adverse penalty at the
wrong grid is `0.05/2 = ₹0.025` per leg against `0.01/2 = ₹0.005` at the real one:
**10.26 bps of round-trip rounding the market does not charge, ≈ 0.051R at a 2% stop —
about 40% of the entire real 25.5 bps charge stack**, and concentrated on exactly the
cheap, tight-stop cohort the research corpus is full of.

⚠ **Blast radius, stated because it was overstated once:** `_round_tick` is called from
`paper_broker` and **nowhere else** — not by the research probes, not by the backtest
engine — and `positions` is empty, so this contaminated no published research number. It
is a before-cycle-2 correctness fix to the simulator, not a restatement of history.

⭐ **Why a TABLE and not `0.01 if price < 250 else 0.05`.** The grid is an exchange
schedule with an effective date: it is owned externally, it has changed once inside our
own data window, and it will change again. Hardcoding the current state as an expression
is precisely the shape **W5** forbids — a value with an owner, copied into code with no
source and no way to tell when it stopped being true. Every row below carries the date it
took effect and the evidence for it.

## The schedule, and where each row comes from

`[measured]` from `ohlcv_1d` itself — the share of daily closes that sit exactly on a
₹0.05 multiple, by price band and quarter. A population fully on a ₹0.01 grid lands on
₹0.05 about **20%** of the time by chance; a population on a ₹0.05 grid lands on it ~100%
of the time (we measure 93–98%, the shortfall being off-grid closes from auctions and
corporate actions).

| period | sub-₹250 on ₹0.05 | ≥₹250 on ₹0.05 |
|---|---|---|
| 2019 Q4 – 2020 Q4 | 96.6 – 97.8% | 96.3 – 97.3% |
| 2023 Q3 – 2024 May | 84.2 – 88.5% | 96.9 – 97.4% |
| **2024 June** | ⭐ **38.98%** | 94.91% |
| 2024 July onward | ⭐ **20.8 – 23.3%** | 93.9 – 95.8% |

⇒ **The change took effect during June 2024 and completed by July; the ≥₹250 band never
moved.** The post-change sub-₹250 figure sitting at ~21% is the chance rate, i.e. that
band is *fully* on ₹0.01.

## ⚠ The boundary is a ZONE, not a cliff — and that is why it is set at ₹225

`[measured]` post-transition (2025 onward), by ₹25 price band:

| band | % on ₹0.05 | reading |
|---|---|---|
| ₹0 – ₹225 | 20.5 – 23.5% | fully ₹0.01 |
| **₹225 – ₹250** | **39.3%** | ⚠ mixed |
| **₹250 – ₹275** | **66.5%** | ⚠ mixed |
| **₹275 – ₹300** | **84.0%** | ⚠ mixed |
| ₹300+ | 95.6 – 99.3% | fully ₹0.05 |

⭐ **A sharp ₹250 cut would be wrong for roughly a third of the ₹225–₹300 zone.** The
pattern is what you get when the tick is a property of the **instrument**, assigned at a
periodic review and sticky afterwards — a name reviewed at ₹240 keeps its ₹0.01 grid while
it trades up through ₹290 — rather than a function of the instantaneous price.

⇒ **So the boundary is placed at ₹225, the measured start of the mixed zone, NOT at ₹250.**
The module's contract is that the model *can only make a fill worse*: assuming the COARSER
₹0.05 grid throughout the ambiguous zone can over-charge a name that is really on ₹0.01,
but can never under-charge one that is really on ₹0.05. Erring the other way would hand us
fills better than reality on up to a third of that band, which is the failure this whole
module exists to prevent.

⚠ **The exact refinement, when it is wanted, is a per-instrument tick column** sourced from
the exchange's own security master. That is a data acquisition, not a modelling choice, and
it is not on the critical path: the cohort the bug actually hurt (₹20–₹80 names) is
unambiguous in every reading above.

⚠ **`valid_from` dates here are DERIVED FROM OUR OWN DATA, not read off a circular.** They
are correct to the month. If the published NSE/SEBI effective date is ever confirmed,
replace the date and the `source` string together — that is what the column is for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# The finest grid observed anywhere in `ohlcv_1d`: 100% of closes in every band and every
# period sit on a ₹0.01 multiple. Nothing below this needs modelling.
FINEST_TICK = Decimal("0.01")

# ⚠ NOT ₹250 — see the module docstring. ₹225 is the measured start of the mixed zone, and
# taking the low end is the choice that can only make a fill worse.
CHEAP_BAND_CEILING = Decimal("225")


@dataclass(frozen=True)
class TickBand:
    """One schedule row: from `valid_from`, prices in `[price_lo, price_hi)` tick at `tick`."""

    valid_from: date
    price_lo: Decimal
    price_hi: Decimal | None  # None = unbounded above
    tick: Decimal
    source: str

    def covers(self, price: Decimal, as_of: date) -> bool:
        return (
            as_of >= self.valid_from
            and price >= self.price_lo
            and (self.price_hi is None or price < self.price_hi)
        )


# Ordered NEWEST-FIRST: `tick_for` takes the first row that covers, so a later schedule
# shadows an earlier one without needing end-dates on every row.
SCHEDULE: tuple[TickBand, ...] = (
    TickBand(
        valid_from=date(2024, 6, 1),
        price_lo=Decimal("0"),
        price_hi=CHEAP_BAND_CEILING,
        tick=Decimal("0.01"),
        source=(
            "[measured] ohlcv_1d: sub-₹250 closes on the ₹0.05 grid fell 85.9% (2024-05) "
            "→ 38.98% (2024-06) → 21.19% (2024-07) and have stayed at the ~20% chance "
            "rate since, while the ≥₹250 band never moved. Boundary at ₹225, the low end "
            "of the measured mixed zone, so the model can only make a fill worse."
        ),
    ),
    TickBand(
        valid_from=date(1900, 1, 1),
        price_lo=Decimal("0"),
        price_hi=None,
        tick=Decimal("0.05"),
        source=(
            "[measured] ohlcv_1d 2019-Q4 → 2024-05: 84–98% of closes on the ₹0.05 grid in "
            "BOTH price bands — one uniform grid. This is also the row that applies at and "
            "above ₹225 today, which is why it carries no upper bound."
        ),
    ),
)


def tick_for(price: Decimal, *, as_of: date) -> Decimal:
    """The tick grid for `price` on `as_of`.

    Falls through the schedule newest-first and returns the first covering row's tick.
    ⚠ A price at or above `CHEAP_BAND_CEILING` is not covered by the 2024 row and falls to
    the base ₹0.05 row — which is the intended behaviour, not a gap.
    """
    for band in SCHEDULE:
        if band.covers(price, as_of):
            return band.tick
    # Unreachable while the base row is unbounded and starts in 1900, but a tick model that
    # silently returns "no rounding" would hand out fills better than reality, so it fails
    # to the COARSEST grid rather than to none.
    return max(b.tick for b in SCHEDULE)
