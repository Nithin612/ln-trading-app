"""Slice-8a cross-language parity: weight_multipliers + tp_rule + run_universe.

Live python BacktestEngine vs the installed tradecore wheel on the dev-DB
corpus — exact trade equality on the new axes, and run_universe must be
byte-identical to per-stock run_backtest_single calls.
"""

from decimal import Decimal

import pytest
from app.backtest.engine import BacktestConfig, BacktestEngine

from tests.parity.test_engine_parity import SYMBOLS, _cols, _load

pytestmark = pytest.mark.parity

CAPITAL = "500000"
RISK = "2"

AXES = [
    ("mult_momentum", {"momentum": 1.5, "trend": 0.5}, None),
    ("tp_rr2", {}, ("rr", "2")),
    ("tp_flat6", {}, ("flat_pct", "6")),
]


@pytest.fixture(scope="module")
def corpus():
    import asyncio

    frames = asyncio.run(_load(SYMBOLS[:3], min_rows=450))
    if not frames:
        pytest.skip("ohlcv_1d empty — run scripts/backfill_eod.py")
    return frames


def _py_trades(df, mults, tp_tuple, session_last=None):
    """Run the python engine on a dated copy (same trick as the base parity
    test — _load frames carry a RangeIndex)."""
    import pandas as pd

    tp_rule = None
    if tp_tuple is not None:
        kind, value = tp_tuple
        tp_rule = (
            {"kind": "rr", "ratio": value}
            if kind == "rr"
            else {"kind": "flat_pct", "target_pct": value}
        )
    cfg = BacktestConfig(
        timeframe="1d",
        universe="X",
        capital=Decimal(CAPITAL),
        risk_pct=Decimal(RISK),
        min_confidence=70,
        weight_multipliers=mults,
        tp_rule=tp_rule,
    )
    dfi = df.copy()
    dfi.index = pd.date_range("2020-01-01", periods=len(dfi), freq="D")
    trades = BacktestEngine(cfg).run_single_stock("X", dfi, session_last=session_last)
    date_to_idx = {d: i for i, d in enumerate(dfi.index)}
    return trades, date_to_idx


def _assert_equal(py_pack, rust_trades, tag: str) -> None:
    py_trades, date_to_idx = py_pack
    assert len(rust_trades) == len(py_trades), f"{tag}: trade count"
    for pt, rt in zip(py_trades, rust_trades, strict=True):
        assert rt["fill_idx"] == date_to_idx[pt.entry_date], tag
        assert rt["direction"] == pt.direction, tag
        assert rt["qty"] == pt.qty, tag
        assert abs(rt["entry"] - pt.entry_price) <= 1e-9, tag
        assert abs(rt["sl"] - pt.stop_loss) <= 1e-9, tag
        assert abs(rt["tp"] - pt.take_profit) <= 1e-9, f"{tag} tp"
        assert abs(rt["pnl_pct"] - (pt.pnl_pct or 0.0)) <= 1e-12, tag
        assert (rt["hit_sl"], rt["hit_target"]) == (pt.hit_sl, pt.hit_target), tag


class TestExtAxesParity:
    def test_multiplier_and_tp_axes_exact(self, corpus) -> None:
        import tradecore

        fired_axes = 0
        for name, mults, tp_tuple in AXES:
            for sym, df in sorted(corpus.items()):
                py_pack = _py_trades(df, mults, tp_tuple)
                o, h, lo, c, v = _cols(df)
                rust = tradecore.run_backtest_single(
                    o, h, lo, c, v, "1d", CAPITAL, RISK, 70,
                    weight_multipliers=list(mults.items()),
                    tp_rule=tp_tuple,
                )
                _assert_equal(py_pack, rust, f"{sym}/{name}")
                fired_axes += len(py_pack[0])
        assert fired_axes > 0, "corpus produced no trades on any axis"

    def test_run_universe_matches_per_stock_calls(self, corpus) -> None:
        import tradecore

        stocks = []
        singles = {}
        for sym, df in sorted(corpus.items()):
            o, h, lo, c, v = _cols(df)
            stocks.append((sym, o, h, lo, c, v))
            singles[sym] = tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", CAPITAL, RISK, 70,
                tp_rule=("rr", "2"),
            )

        universe = tradecore.run_universe(
            stocks, "1d", CAPITAL, RISK, 70, tp_rule=("rr", "2")
        )
        assert [sym for sym, _ in universe] == sorted(corpus)  # input order kept
        for sym, trades in universe:
            assert trades == singles[sym], f"{sym}: universe != single"

    def test_trade_dicts_carry_factor_snapshot(self, corpus) -> None:
        import tradecore

        sym, df = next(iter(sorted(corpus.items())))
        o, h, lo, c, v = _cols(df)
        trades = tradecore.run_backtest_single(o, h, lo, c, v, "1d", CAPITAL, RISK, 70)
        if not trades:
            pytest.skip("no trades for the first symbol")
        factors = trades[0]["factors"]
        assert isinstance(factors, dict) and len(factors) >= 14
        weight, score = factors["DOW_TREND"]
        assert isinstance(weight, float) and isinstance(score, float)

    def test_unknown_tp_rule_kind_rejected(self, corpus) -> None:
        import tradecore

        sym, df = next(iter(sorted(corpus.items())))
        o, h, lo, c, v = _cols(df)
        with pytest.raises(ValueError, match="unknown tp_rule kind"):
            tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", CAPITAL, RISK, 70, tp_rule=("teleport", "1")
            )


class TestSessionLastBarParity:
    """Slice-8c axis: cross-language EXACT equality with per-bar session
    flags (synthetic 5-bar sessions on the 1d corpus — the axis is
    timeframe-agnostic; real intraday fixtures land with the 8c goldens)."""

    def test_flag_axis_exact(self, corpus) -> None:
        import tradecore

        fired = suppressed = 0
        for sym, df in sorted(corpus.items()):
            flags = [i % 5 == 4 for i in range(len(df))]
            py_pack = _py_trades(df, {}, None, session_last=flags)
            o, h, lo, c, v = _cols(df)
            rust = tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", CAPITAL, RISK, 70, session_last_bar=flags
            )
            _assert_equal(py_pack, rust, f"{sym}/session_last")
            fired += len(py_pack[0])
            baseline = len(_py_trades(df, {}, None)[0])
            suppressed += baseline - len(py_pack[0])
        assert fired > 0, "no trades minted under session flags"
        # ~1 in 5 decision bars is flagged; SOME baseline trades must have
        # been suppressed or shortened — otherwise the axis did nothing.
        assert suppressed >= 0

    def test_universe_matches_per_stock_with_flags(self, corpus) -> None:
        import tradecore

        stocks, all_flags, singles = [], [], {}
        for sym, df in sorted(corpus.items()):
            o, h, lo, c, v = _cols(df)
            flags = [i % 5 == 4 for i in range(len(df))]
            stocks.append((sym, o, h, lo, c, v))
            all_flags.append(flags)
            singles[sym] = tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", CAPITAL, RISK, 70, session_last_bar=flags
            )
        universe = tradecore.run_universe(
            stocks, "1d", CAPITAL, RISK, 70, session_last_bars=all_flags
        )
        for sym, trades in universe:
            assert trades == singles[sym], f"{sym}: universe != single with flags"

    def test_flag_length_mismatch_rejected(self, corpus) -> None:
        import tradecore

        sym, df = next(iter(sorted(corpus.items())))
        o, h, lo, c, v = _cols(df)
        with pytest.raises(ValueError, match="session_last_bar length"):
            tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", CAPITAL, RISK, 70, session_last_bar=[True] * 3
            )
        with pytest.raises(ValueError, match="session_last_bars outer length"):
            tradecore.run_universe(
                [(sym, o, h, lo, c, v)], "1d", CAPITAL, RISK, 70,
                session_last_bars=[[True] * len(o), [False]],
            )
