"""Regression tests for the 100x position-sizing bug (Phase 0 triage).

signal_tasks used to pre-divide default_risk_per_trade_pct by 100 before
handing it to the signal service, whose compute_quantity divides by 100
again (SIGNAL_ENGINE.md §6). Net effect: every Celery-generated signal
risked 0.02% of capital instead of 2%.
"""

from decimal import Decimal

import pytest
from app.analysis.risk import compute_quantity
from app.tasks.signal_tasks import _default_risk_params


class TestDefaultRiskParams:
    def test_risk_pct_is_whole_percentage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "default_risk_per_trade_pct", 2.0)
        _, risk_pct = _default_risk_params()
        assert risk_pct == Decimal("2.0")  # NOT 0.02

    def test_end_to_end_quantity_at_intended_risk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Capital ₹5,00,000 at 2% risk with ₹2/share risk → 5000 shares."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "default_risk_per_trade_pct", 2.0)
        capital, risk_pct = _default_risk_params()
        qty = compute_quantity(
            capital=capital,
            risk_pct=risk_pct,
            entry=Decimal("100"),
            stop_loss=Decimal("98"),
        )
        assert qty == 5000

    def test_bug_canary_hundredfold_undersizing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The buggy chain produced qty=50 for the scenario above."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "default_risk_per_trade_pct", 2.0)
        capital, risk_pct = _default_risk_params()
        qty = compute_quantity(capital, risk_pct, Decimal("100"), Decimal("98"))
        assert qty != 50


class TestGenerateEndpointRiskPct:
    """Regression (Phase-2 slice 0): POST /signals/generate defaulted
    risk_pct=0.02 — fractional style in a whole-percent convention, the same
    family as the Phase-0 100× bug, live on the admin endpoint. The default
    is now 2.0 and fractional-style values are rejected, not resized."""

    def test_default_is_whole_percent(self) -> None:
        from app.api.v1.signals import GenerateRequest

        req = GenerateRequest(stock_id=1)
        assert req.risk_pct == Decimal("2.0")  # NOT 0.02

    def test_old_fractional_default_is_rejected(self) -> None:
        """Canary: the old default value must now fail validation loudly."""
        from app.api.v1.signals import GenerateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GenerateRequest(stock_id=1, risk_pct=Decimal("0.02"))

    def test_bounds(self) -> None:
        from app.api.v1.signals import GenerateRequest
        from pydantic import ValidationError

        assert GenerateRequest(stock_id=1, risk_pct=Decimal("0.1")).risk_pct == Decimal("0.1")
        assert GenerateRequest(stock_id=1, risk_pct=Decimal("10")).risk_pct == Decimal("10")
        with pytest.raises(ValidationError):
            GenerateRequest(stock_id=1, risk_pct=Decimal("10.5"))
        with pytest.raises(ValidationError):
            GenerateRequest(stock_id=1, risk_pct=Decimal("0"))
