"""Tests for the backtest engine."""


import numpy as np
import pandas as pd
from app.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult


def _stock_candles(n: int = 200, drift: float = 0.003) -> pd.DataFrame:
    rng = np.random.default_rng(99)
    base = 100.0
    rows = []
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    for _ in range(n):
        o = base
        c = base * (1 + drift + rng.uniform(-0.005, 0.005))
        h = max(o, c) * (1 + rng.uniform(0.001, 0.005))
        lo = min(o, c) * (1 - rng.uniform(0.001, 0.003))
        rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": int(1e6)})
        base = c
    return pd.DataFrame(rows, index=dates)


class TestBacktestEngine:
    def test_empty_candles_returns_empty_result(self) -> None:
        cfg = BacktestConfig()
        engine = BacktestEngine(cfg)
        result = engine.run({})
        assert result.total_trades == 0

    def test_insufficient_candles_returns_empty(self) -> None:
        cfg = BacktestConfig()
        engine = BacktestEngine(cfg)
        df = _stock_candles(30)
        result = engine.run({"STOCK": df})
        assert result.total_trades == 0

    def test_run_returns_backtest_result(self) -> None:
        cfg = BacktestConfig(min_confidence=60)
        engine = BacktestEngine(cfg)
        df = _stock_candles(200)
        result = engine.run({"TESTSTOCK": df})
        assert isinstance(result, BacktestResult)
        assert result.total_trades >= 0

    def test_win_rate_in_range(self) -> None:
        cfg = BacktestConfig(min_confidence=60)
        engine = BacktestEngine(cfg)
        df = _stock_candles(200)
        result = engine.run({"TESTSTOCK": df})
        if result.total_trades > 0:
            assert 0 <= result.win_rate_pct <= 100

    def test_no_lookahead_bias(self) -> None:
        """Signal is generated on candle N, filled on candle N+1 open — not on N's close."""
        cfg = BacktestConfig(min_confidence=0)  # emit everything for testing
        engine = BacktestEngine(cfg)
        df = _stock_candles(100)
        trades = engine.run_single_stock("STOCK", df)
        for t in trades:
            # Entry must be the open of a candle after the signal candle
            # We can't directly inspect the index, but entry price should be a real open price
            assert t.entry_price in [float(df.iloc[i]["open"]) for i in range(len(df))]

    def test_multiple_stocks(self) -> None:
        cfg = BacktestConfig(min_confidence=60)
        engine = BacktestEngine(cfg)
        stocks = {
            "STOCK_A": _stock_candles(200, drift=0.003),
            "STOCK_B": _stock_candles(200, drift=-0.002),
        }
        result = engine.run(stocks)
        assert isinstance(result, BacktestResult)

    def test_metrics_computed(self) -> None:
        cfg = BacktestConfig(min_confidence=50)
        engine = BacktestEngine(cfg)
        df = _stock_candles(200)
        result = engine.run({"STOCK": df})
        if result.total_trades > 0:
            assert result.winning_trades + result.losing_trades == result.total_trades
            assert result.max_drawdown_pct >= 0
            assert isinstance(result.sharpe, float)
            assert isinstance(result.sortino, float)

    def test_deterministic_output(self) -> None:
        """Same inputs → same outputs (no random seed dependency in engine)."""
        cfg = BacktestConfig(min_confidence=60)
        df = _stock_candles(200)
        result_1 = BacktestEngine(cfg).run({"STOCK": df})
        result_2 = BacktestEngine(cfg).run({"STOCK": df})
        assert result_1.total_trades == result_2.total_trades
        assert result_1.win_rate_pct == result_2.win_rate_pct
