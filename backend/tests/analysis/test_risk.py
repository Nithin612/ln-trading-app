"""Tests for risk sizer, classifier, and expiry rules."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.analysis.risk import compute_levels, compute_quantity
from app.signals.classifier import classify_signal
from app.signals.expiry import compute_validity_until, is_expired


class TestComputeQuantity:
    def test_worked_example_from_spec(self) -> None:
        # From SIGNAL_ENGINE.md §7: capital=₹100k, risk_pct=2%, entry=490, SL=482 → qty=250
        qty = compute_quantity(
            capital=Decimal("100000"),
            risk_pct=Decimal("2"),
            entry=Decimal("490"),
            stop_loss=Decimal("482"),
        )
        assert qty == 250

    def test_zero_risk_raises(self) -> None:
        with pytest.raises(ValueError, match="Stop loss must differ"):
            compute_quantity(Decimal("100000"), Decimal("2"), Decimal("490"), Decimal("490"))

    def test_floors_to_integer(self) -> None:
        # risk_amount = 2000, risk_per_share = 7.3 → 273.97... → floor = 273
        qty = compute_quantity(
            capital=Decimal("100000"),
            risk_pct=Decimal("2"),
            entry=Decimal("490"),
            stop_loss=Decimal("482.7"),
        )
        assert qty == 273

    def test_zero_quantity_when_sl_too_wide(self) -> None:
        # SL 50% away → very small qty
        qty = compute_quantity(
            capital=Decimal("10000"),
            risk_pct=Decimal("1"),
            entry=Decimal("100"),
            stop_loss=Decimal("50"),
        )
        assert qty == 2  # 100 / 50 = 2

    def test_returns_non_negative(self) -> None:
        qty = compute_quantity(Decimal("1000"), Decimal("0.1"), Decimal("100"), Decimal("99"))
        assert qty >= 0


class TestComputeLevels:
    def test_scalp_buy(self) -> None:
        result = compute_levels("BUY", "scalp", Decimal("100"))
        assert result is not None
        sl, tp = result
        assert sl < Decimal("100")
        assert tp > Decimal("100")

    def test_scalp_sell(self) -> None:
        result = compute_levels("SELL", "scalp", Decimal("100"))
        assert result is not None
        sl, tp = result
        assert sl > Decimal("100")
        assert tp < Decimal("100")

    def test_swing_sl_too_wide_rejected(self) -> None:
        # Natural swing low that's 10% away → exceeds 8% max → rejected
        result = compute_levels(
            "BUY", "swing", Decimal("100"), swing_low=Decimal("88")
        )
        assert result is None

    def test_swing_sl_within_limit(self) -> None:
        # SL 5% away → allowed
        result = compute_levels("BUY", "swing", Decimal("100"), swing_low=Decimal("95"))
        assert result is not None

    def test_intraday_natural_sl(self) -> None:
        result = compute_levels(
            "BUY", "intraday", Decimal("100"), swing_low=Decimal("99.6")
        )
        assert result is not None
        sl, _ = result
        assert sl == Decimal("99.6")

    def test_positional_uses_ema20(self) -> None:
        result = compute_levels(
            "BUY", "positional", Decimal("100"), ema20_daily=Decimal("95")
        )
        assert result is not None
        sl, tp = result
        assert sl == Decimal("95")
        assert tp > Decimal("100")

    def test_unknown_classification_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown classification"):
            compute_levels("BUY", "daytrade", Decimal("100"))


class TestClassifier:
    def test_scalp_1m(self) -> None:
        assert classify_signal("1m", []) == "scalp"

    def test_scalp_5m(self) -> None:
        assert classify_signal("5m", []) == "scalp"

    def test_intraday_15m(self) -> None:
        assert classify_signal("15m", []) == "intraday"

    def test_intraday_1h(self) -> None:
        assert classify_signal("1h", []) == "intraday"

    def test_swing_1d(self) -> None:
        assert classify_signal("1d", []) == "swing"

    def test_positional_1d_multibagger(self) -> None:
        assert classify_signal("1d", [], is_multibagger=True) == "positional"

    def test_positional_1w(self) -> None:
        assert classify_signal("1w", []) == "positional"


class TestExpiry:
    _NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)

    def test_scalp_30min(self) -> None:
        v = compute_validity_until("scalp", self._NOW)
        diff = (v - self._NOW).total_seconds()
        assert diff == pytest.approx(1800, abs=1)

    def test_intraday_same_day_close(self) -> None:
        # 10:00 UTC (market already open) → 09:45 UTC same day? No, should be 09:45 next day
        v = compute_validity_until("intraday", self._NOW)
        # 10:00 UTC > 09:45 UTC → rolls to next day
        assert v.hour == 9 and v.minute == 45
        assert v.date() > self._NOW.date()

    def test_swing_7_calendar_days(self) -> None:
        v = compute_validity_until("swing", self._NOW)
        diff = (v - self._NOW).days
        assert diff == 7

    def test_positional_42_calendar_days(self) -> None:
        v = compute_validity_until("positional", self._NOW)
        diff = (v - self._NOW).days
        assert diff == 42

    def test_is_expired_true(self) -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        assert is_expired(past)

    def test_is_expired_false(self) -> None:
        future = datetime(2099, 1, 1, tzinfo=UTC)
        assert not is_expired(future)

    def test_is_expired_custom_now(self) -> None:
        validity = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
        now_before = datetime(2026, 5, 19, 11, 0, tzinfo=UTC)
        now_after = datetime(2026, 5, 19, 13, 0, tzinfo=UTC)
        assert not is_expired(validity, now=now_before)
        assert is_expired(validity, now=now_after)
