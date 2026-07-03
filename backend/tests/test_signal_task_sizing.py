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
