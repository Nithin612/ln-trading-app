"""session_last_bar freeze-extension (Phase 2 slice 8c) — python side.

The axis is default-off: session_last=None is byte-identical to the frozen
engine (the untouched oracle fixtures prove it at the suite level). These
tests pin the NEW semantics directly on _simulate_trade (no confluence
needed) and the data-driven flag helper. Cross-language equality is pinned
by the parity suite; rust-side unit tests live in
engine/crates/engine-core/tests/session_last_bar.rs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from app.backtest.engine import BacktestConfig, BacktestEngine
from app.backtest.walkforward import session_last_flags


def _candles(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["volume"] = 1000.0
    df.index = pd.date_range("2026-01-01 09:15", periods=len(df), freq="5min")
    return df


def _engine() -> BacktestEngine:
    return BacktestEngine(BacktestConfig(capital=Decimal("500000"), risk_pct=Decimal("2")))


# Quiet bars: SL 90 / TP 120 never touched (low 99, high 101).
_QUIET = [(100.0, 101.0, 99.0, 100.5)] * 8


class TestSessionCloseOut:
    def test_open_trade_exits_at_flagged_bar_close(self) -> None:
        flags = [False] * 8
        flags[4] = True
        trade = _engine()._simulate_trade(
            stock="X", signal_candle_idx=1, direction="BUY", classification="intraday",
            confidence_pct=75, stop_loss=90.0, take_profit=120.0, qty=10,
            candles=_candles(_QUIET), session_last=flags,
        )
        assert trade is not None
        assert trade.exit_date == _candles(_QUIET).index[4]
        assert trade.exit_price == 100.5
        assert not trade.hit_sl and not trade.hit_target
        assert trade.pnl_pct == pytest.approx((100.5 - 100.0) / 100.0 * 100, abs=1e-12)

    def test_sell_side_sign(self) -> None:
        flags = [False] * 8
        flags[3] = True
        trade = _engine()._simulate_trade(
            stock="X", signal_candle_idx=1, direction="SELL", classification="intraday",
            confidence_pct=75, stop_loss=110.0, take_profit=80.0, qty=10,
            candles=_candles(_QUIET), session_last=flags,
        )
        assert trade is not None
        assert trade.exit_price == 100.5
        assert trade.pnl_pct == pytest.approx(-(100.5 - 100.0) / 100.0 * 100, abs=1e-12)

    def test_stop_loss_beats_session_exit_on_the_same_bar(self) -> None:
        rows = list(_QUIET)
        rows[4] = (100.0, 101.0, 89.0, 100.5)  # low pierces SL 90 on the flagged bar
        flags = [False] * 8
        flags[4] = True
        trade = _engine()._simulate_trade(
            stock="X", signal_candle_idx=1, direction="BUY", classification="intraday",
            confidence_pct=75, stop_loss=90.0, take_profit=120.0, qty=10,
            candles=_candles(rows), session_last=flags,
        )
        assert trade is not None
        assert trade.hit_sl and trade.exit_price == 90.0  # the stop, not the close

    def test_none_keeps_frozen_end_of_data_behavior(self) -> None:
        trade = _engine()._simulate_trade(
            stock="X", signal_candle_idx=1, direction="BUY", classification="intraday",
            confidence_pct=75, stop_loss=90.0, take_profit=120.0, qty=10,
            candles=_candles(_QUIET), session_last=None,
        )
        assert trade is not None
        assert trade.exit_date == _candles(_QUIET).index[-1]  # end-of-data close-out

    def test_length_mismatch_rejected_loudly(self) -> None:
        df = _candles(_QUIET * 8)  # 64 bars ≥ warm-up
        with pytest.raises(ValueError, match="session_last length"):
            _engine().run_single_stock("X", df, session_last=[True] * 3)


class TestSessionLastFlags:
    def test_flags_mark_session_boundaries_and_final_bar(self) -> None:
        d1, d2, d3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5)
        dates = [d1, d1, d1, d2, d2, d3]
        assert session_last_flags(dates) == [False, False, True, False, True, True]

    def test_half_day_session_is_data_driven(self) -> None:
        # A one-bar (muhurat-like) session flags its only bar.
        d1, d2 = date(2026, 10, 21), date(2026, 10, 22)
        assert session_last_flags([d1, d2, d2]) == [True, False, True]

    def test_empty_and_single(self) -> None:
        assert session_last_flags([]) == []
        assert session_last_flags([date(2026, 1, 1)]) == [True]
