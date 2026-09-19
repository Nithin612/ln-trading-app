"""Item 20 — capital-gains tax, and the correction that reframed it.

⛔⛔ The queue originally carried tax as a cost to ADD to break-even. It is levied on PROFIT,
so at break-even it is zero and **break-even does not move**. What it moves is every TARGET.
Adding it to the cost stack would have made every break-even figure in the programme — item
5's included — too pessimistic. The first test below is that correction, asserted.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.trading.tax import (
    LONG_TERM_DAYS,
    SLAB_UNKNOWN,
    TAX_HISTORY,
    capital_gains_tax,
    holding_class,
    pretax_target_for,
    schedule_for,
)

OLD = date(2024, 1, 10)   # before the Budget-2024 change
NEW = date(2025, 1, 10)   # after it


# ── The correction ───────────────────────────────────────────────────────────

def test_tax_is_zero_at_break_even_so_break_even_does_not_move() -> None:
    """⭐⭐ ITEM 20's WHOLE POINT. If this were non-zero, tax would belong in the cost stack
    and every break-even in the programme would be wrong."""
    assert capital_gains_tax(Decimal("0"), entry_on=OLD, exit_on=NEW) == Decimal("0.00")


def test_a_loss_is_never_taxed() -> None:
    assert capital_gains_tax(Decimal("-5000"), entry_on=OLD, exit_on=NEW) == Decimal("0.00")


def test_what_tax_actually_does_is_raise_the_target() -> None:
    """A ₹10,000 NET short-term gain needs more than ₹10,000 GROSS — and nothing in the
    system said so before this."""
    gross = pretax_target_for(Decimal("10000"), entry_on=date(2024, 12, 1), exit_on=NEW)
    assert isinstance(gross, Decimal)
    assert gross > Decimal("10000")
    # 20% + 4% cess = 20.8% effective ⇒ 10000 / 0.792
    assert gross == Decimal("12626.26")


def test_the_target_round_trips_back_to_the_after_tax_figure() -> None:
    """The two directions must agree, or one of them is decoration."""
    after = Decimal("10000")
    gross = pretax_target_for(after, entry_on=date(2024, 12, 1), exit_on=NEW)
    assert isinstance(gross, Decimal)
    tax = capital_gains_tax(gross, entry_on=date(2024, 12, 1), exit_on=NEW)
    assert isinstance(tax, Decimal)
    assert abs((gross - tax) - after) < Decimal("0.02")


# ── Effective dating — the rate change inside our own test block ─────────────

def test_the_budget_2024_change_is_dated_and_both_regimes_are_modelled() -> None:
    """⭐⭐ The change took effect 2024-07-23 and the test block runs from 2023-07-03, so
    BOTH regimes sit inside the window. A single-rate model would be wrong for roughly its
    first year — which is why this mirrors A23's effective-dated fee schedules."""
    before = schedule_for(date(2024, 7, 22))
    after = schedule_for(date(2024, 7, 23))

    assert before.short_term_rate == Decimal("0.15")
    assert after.short_term_rate == Decimal("0.20")
    assert before.long_term_rate == Decimal("0.10")
    assert after.long_term_rate == Decimal("0.125")
    assert before.long_term_exemption == Decimal("100000")
    assert after.long_term_exemption == Decimal("125000")


def test_the_same_gain_is_taxed_differently_either_side_of_the_change() -> None:
    gain = Decimal("100000")
    old = capital_gains_tax(gain, entry_on=date(2024, 1, 1), exit_on=date(2024, 7, 22))
    new = capital_gains_tax(gain, entry_on=date(2024, 1, 1), exit_on=date(2024, 7, 23))
    assert old == Decimal("15600.00")   # 15% + 4% cess
    assert new == Decimal("20800.00")   # 20% + 4% cess


def test_a_date_before_coverage_raises_rather_than_silently_using_the_oldest() -> None:
    """A rate we cannot source is unknown, and unknown must be loud — same contract as
    `fees.schedule_for`."""
    with pytest.raises(ValueError, match="no tax schedule covers"):
        schedule_for(date(2010, 1, 1))


def test_the_history_is_append_only_and_ascending() -> None:
    dates = [e.effective_from for e in TAX_HISTORY]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)


# ── Classification ───────────────────────────────────────────────────────────

def test_more_than_twelve_months_is_long_term() -> None:
    entry = date(2023, 1, 1)
    assert holding_class(entry, entry.replace(year=2024), "delivery") == "short_term"
    assert holding_class(entry, date(2024, 1, 2), "delivery") == "long_term"
    assert (date(2024, 1, 2) - entry).days == LONG_TERM_DAYS + 1


def test_intraday_is_decided_by_product_not_by_the_dates() -> None:
    """⚠ A delivery trade opened and closed the same session is still a CAPITAL GAIN; an MIS
    trade is speculative business income however it is held."""
    same_day = date(2025, 3, 3)
    assert holding_class(same_day, same_day, "delivery") == "short_term"
    assert holding_class(same_day, same_day, "intraday") == "intraday"


def test_intraday_returns_slab_unknown_rather_than_a_guessed_rate() -> None:
    """⛔ Speculative business income is taxed at the individual's slab together with all
    other income — there is no flat rate to encode, and inventing one would fabricate
    precision the way an invented per-trade cost floor would."""
    assert capital_gains_tax(
        Decimal("5000"), entry_on=NEW, exit_on=NEW, product="intraday"
    ) == SLAB_UNKNOWN
    assert pretax_target_for(
        Decimal("5000"), entry_on=NEW, exit_on=NEW, product="intraday"
    ) == SLAB_UNKNOWN


# ── The long-term exemption ──────────────────────────────────────────────────

def test_a_long_term_gain_below_the_exemption_is_untaxed() -> None:
    tax = capital_gains_tax(
        Decimal("100000"), entry_on=date(2023, 1, 1), exit_on=date(2025, 1, 2)
    )
    assert tax == Decimal("0.00"), "₹1L is below the ₹1.25L post-2024 exemption"


def test_only_the_excess_over_the_exemption_is_taxed() -> None:
    tax = capital_gains_tax(
        Decimal("225000"), entry_on=date(2023, 1, 1), exit_on=date(2025, 1, 2)
    )
    # (225000 - 125000) x 12.5% x 1.04
    assert tax == Decimal("13000.00")


def test_the_exemption_can_be_threaded_across_disposals() -> None:
    """⚠ The allowance is ANNUAL, not per-trade. Priced in isolation, the second long-term
    disposal of a year is under-taxed — so a caller can say how much is already spent."""
    used_up = capital_gains_tax(
        Decimal("100000"), entry_on=date(2023, 1, 1), exit_on=date(2025, 1, 2),
        long_term_exemption_used=Decimal("125000"),
    )
    assert used_up == Decimal("13000.00")   # no allowance left ⇒ the whole gain is taxed
