"""Queue item 4 — tests for the entry-bar gap finder.

⭐ The centrepiece is `test_the_frozen_engine_books_exactly_plus_one_r_at_every_gap_size`: it CALLS
the frozen `_simulate_trade` (never reimplements it), computes R the way `tp_geometry_study`,
`rvol_factor_study` and `positional_probe` actually compute it, and pins M64's result — +1.0000R
regardless of gap size. That is what makes the contamination invisible in the R distribution, and
therefore what makes this finder necessary rather than merely convenient.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from app.backtest.engine import BacktestConfig, BacktestEngine, TradeRecord
from app.backtest.entry_gap import (
    apply_delete_treatment,
    is_unfillable,
    partition,
)

SIGNAL_CLOSE = 100.0
STOP = 99.0


def _panel(gap_open: float) -> pd.DataFrame:
    """Three bars. Bar 0 closes at 100; bar 1 OPENS at `gap_open`, already through the 99 stop."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [
        (SIGNAL_CLOSE, SIGNAL_CLOSE, SIGNAL_CLOSE, SIGNAL_CLOSE),
        (gap_open, max(gap_open, STOP + 0.5), gap_open - 1, gap_open),
        (gap_open, gap_open + 1, gap_open - 1, gap_open),
    ]
    return pd.DataFrame(
        {
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1e6] * 3,
        },
        index=[base + timedelta(days=i) for i in range(3)],
    )


def _record(gap_open: float, direction: str = "BUY") -> TradeRecord:
    eng = BacktestEngine(BacktestConfig(capital=100_000, risk_pct=2.0))
    rec = eng._simulate_trade(
        "TESTCO", 0, direction, "swing", 75, STOP, 110.0, 10, _panel(gap_open)
    )
    assert rec is not None
    return rec


def _study_r(rec: TradeRecord) -> float:
    """R exactly as D5/D1/positional compute it: pnl% over FILL-referenced risk%."""
    risk_pct = abs(rec.entry_price - rec.stop_loss) / rec.entry_price * 100.0
    assert rec.pnl_pct is not None
    return rec.pnl_pct / risk_pct


@pytest.mark.parametrize("gap_open", [98.0, 95.0, 90.0, 80.0])
def test_the_frozen_engine_books_exactly_plus_one_r_at_every_gap_size(
    gap_open: float,
) -> None:
    """⭐⭐ M64, pinned. The bias is a CONSTANT, not a distribution — which is why an affected
    trade is indistinguishable from a genuine +1R winner and cannot be found by scanning R."""
    rec = _record(gap_open)

    assert rec.hit_sl is True
    assert rec.pnl_pct is not None and rec.pnl_pct > 0, (
        "a stopped-out trade booked a PROFIT — this is the defect"
    )
    assert _study_r(rec) == pytest.approx(1.0, abs=1e-9), (
        "the studies' own R is not exactly +1.0000 — M64's identity has changed"
    )


@pytest.mark.parametrize("gap_open", [98.0, 95.0, 80.0])
def test_the_finder_catches_what_r_cannot(gap_open: float) -> None:
    assert is_unfillable(_record(gap_open)) is True


def test_the_short_mirror_is_caught_too() -> None:
    """A SELL gapping UP through its stop is the same defect with the inequality flipped."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [
        (100.0, 100.0, 100.0, 100.0),
        (105.0, 106.0, 100.5, 105.0),
        (105.0, 106.0, 104.0, 105.0),
    ]
    panel = pd.DataFrame(
        {
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1e6] * 3,
        },
        index=[base + timedelta(days=i) for i in range(3)],
    )
    eng = BacktestEngine(BacktestConfig(capital=100_000, risk_pct=2.0))
    rec = eng._simulate_trade("TESTCO", 0, "SELL", "swing", 75, 101.0, 90.0, 10, panel)

    assert rec is not None
    assert is_unfillable(rec) is True


def test_an_ordinary_trade_is_not_flagged() -> None:
    """The canary against a finder that flags everything — which would 'fix' the corpus by
    emptying it."""
    rec = _record(99.5)  # opens ABOVE the 99 stop: a real, fillable trade
    assert is_unfillable(rec) is False


def test_a_fill_exactly_on_the_stop_is_refused() -> None:
    """Live's rule is `price <= stop_loss` for a long, and it is also the case where
    fill-referenced R is undefined (division by zero)."""
    rec = _record(STOP)
    assert rec.entry_price == pytest.approx(STOP)
    assert is_unfillable(rec) is True


def test_partition_separates_and_conserves() -> None:
    records = [_record(g) for g in (99.5, 95.0, 99.8, 80.0)]
    tradeable, refused = partition(records)

    assert len(tradeable) == 2 and len(refused) == 2
    assert len(tradeable) + len(refused) == len(records), "trades were lost in the partition"


def test_delete_treatment_reports_a_negative_shift() -> None:
    """Every removed trade contributed exactly +1.000R, so deleting them can only pull the mean
    DOWN. A positive shift would mean the finder is flagging the wrong rows."""
    records = [_record(99.5), _record(95.0), _record(99.8)]
    values = [-0.5, 1.0, -0.4]  # the middle one is the contaminated +1R

    out = apply_delete_treatment(records, values)

    assert out.n_before == 3
    assert out.n_dropped == 1
    assert out.mean_after == pytest.approx(-0.45)
    assert out.shift < 0, out.line()
    assert "delete treatment" in out.line()


def test_mismatched_lengths_raise_rather_than_zip_short() -> None:
    """`zip` truncates silently, which would drop the tail of a corpus without saying so."""
    with pytest.raises(ValueError, match="records against"):
        apply_delete_treatment([_record(95.0)], [1.0, 2.0])
