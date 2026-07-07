"""Regression: degenerate stop loss must reject, never crash the run.

Bug (Phase-2 gate, bug-hunter MEDIUM): a pivot swing-low exactly equal to
the last close passes compute_levels' class-cap check (0% ≤ cap) and then
compute_quantity raises ValueError("Stop loss must differ from entry
price") — which propagated through run_profile and killed the WHOLE
nightly suggestions task (current profile's signals rolled back, later
profiles never ran). safe_levels gives the live paths the same
reject-don't-crash semantics the backtest engines always had.
"""

from __future__ import annotations

from decimal import Decimal

from app.signals.risk_guards import safe_levels


class TestSafeLevels:
    def test_degenerate_sl_equal_to_entry_rejected(self) -> None:
        """The exact crash pair: BUY with swing_low == entry gave
        stop_loss == entry (0% distance) then a ValueError downstream."""
        entry = Decimal("482.5000")
        assert safe_levels("BUY", "swing", entry, swing_low=entry, swing_high=None) is None

    def test_wrong_side_sl_rejected_for_sell(self) -> None:
        entry = Decimal("100.0000")
        assert (
            safe_levels("SELL", "swing", entry, swing_low=None, swing_high=entry) is None
        )

    def test_normal_levels_pass_through(self) -> None:
        levels = safe_levels(
            "BUY",
            "swing",
            Decimal("100.0000"),
            swing_low=Decimal("96.0000"),
            swing_high=None,
        )
        assert levels is not None
        stop_loss, take_profit = levels
        assert stop_loss < Decimal("100.0000") < take_profit
        assert stop_loss == Decimal("96.0000")

    def test_class_cap_rejection_preserved(self) -> None:
        """safe_levels must not weaken reject-don't-clamp: a swing SL
        beyond the 8% cap still rejects."""
        assert (
            safe_levels(
                "BUY",
                "swing",
                Decimal("100.0000"),
                swing_low=Decimal("85.0000"),  # 15% away — beyond the 8% cap
                swing_high=None,
            )
            is None
        )
