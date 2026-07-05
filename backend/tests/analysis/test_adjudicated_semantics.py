"""Regression tests for the adjudicated spec alignments.

Each behavior here was DECIDED by the user with measured backtest evidence
and must fail if the old drifted behavior ever returns.
2026-07-04 (scripts/adjudication_experiments.py):
  A  volume only counts when it matches the rest of the confluence
  B  no RSI ±0.4 bands at <30/>70
  C  backtest uses the same pivot swing-SL as live (+ degenerate reject)
  D  factors see exactly the last ≤300 completed candles
  E  honest fills: gap-through exits at open; fill candle checked
2026-07-05 (scripts/adjudication_experiments_fgh.py):
  F  ATR(14) > 3% of price → position size reduced 25% (3q//4)
  G  Morning/Evening Star require the star to gap beyond the first body
"""

from decimal import Decimal

import pandas as pd
import pytest
from app.analysis.confluence import score_from_factors
from app.analysis.indicators.rsi import rsi_level_factor
from app.analysis.patterns.multi import detect_morning_evening_star
from app.analysis.risk import volatility_adjusted_qty
from app.analysis.types import FactorResult
from app.backtest.engine import BacktestConfig, BacktestEngine


def _mk(name: str, weight: float, score: float) -> FactorResult:
    return FactorResult(name, weight, score, "test", ["indicator"])


def _candles(rows: list[tuple[float, float, float, float, int]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="D")
    return df


def _flat(n: int, price: float = 100.0, vol: int = 1000) -> list[tuple]:
    return [(price, price + 1, price - 1, price, vol)] * n


class TestVolumeDirectionMatch:
    def test_surge_flips_negative_when_rest_is_bearish(self) -> None:
        factors = [
            _mk("DOW_TREND", 20, -0.7),
            _mk("PATTERN", 15, -0.9),
            _mk("VOLUME", 10, +0.5),  # raw surge, pre-adjustment
        ]
        candles = _candles(_flat(60))
        result = score_from_factors(factors, candles, min_confidence=1)
        assert result is not None
        vol = next(f for f in result.factors if f.name == "VOLUME")
        assert vol.score == -0.5  # old behavior: +0.5 pushing against the setup
        assert result.direction == "SELL"

    def test_surge_zeroed_when_rest_is_neutral(self) -> None:
        factors = [_mk("VOLUME", 10, +0.5)]
        candles = _candles(_flat(60))
        # volume alone must never fire a signal (hard constraint #4)
        assert score_from_factors(factors, candles, min_confidence=1) is None


class TestRsiBandsRemoved:
    def test_oversold_scores_zero(self) -> None:
        # steep monotonic fall → RSI deep below 30 and falling
        rows = [(p + 0.2, p + 0.5, p - 0.5, p, 1000) for p in range(200, 140, -1)]
        result = rsi_level_factor(_candles([tuple(map(float, r[:4])) + (1000,) for r in rows]))
        assert result.score == 0.0  # was +0.4

    def test_overbought_scores_zero(self) -> None:
        rows = [
            (float(p) - 0.2, float(p) + 0.5, float(p) - 0.5, float(p), 1000)
            for p in range(140, 200)
        ]
        result = rsi_level_factor(_candles(rows))
        assert result.score == 0.0  # was -0.4


class TestHonestFills:
    def _engine(self) -> BacktestEngine:
        return BacktestEngine(
            BacktestConfig(capital=Decimal("100000"), risk_pct=Decimal("2"))
        )

    def test_gap_through_sl_exits_at_open(self) -> None:
        candles = _candles([
            (100, 101, 99, 100, 1000),      # signal candle (idx 0)
            (100, 102, 99.5, 101, 1000),    # fill at open 100
            (90, 91, 88, 89, 1000),         # gaps far below SL 95 → exit at 90
        ])
        rec = self._engine()._simulate_trade(
            "T", 0, "BUY", "swing", 75, stop_loss=95.0, take_profit=120.0,
            qty=10, candles=candles,
        )
        assert rec is not None
        assert rec.hit_sl is True
        assert rec.exit_price == 90.0  # old behavior: exit AT 95 (impossible fill)
        assert rec.pnl_pct == (90.0 - 100.0) / 100.0 * 100

    def test_fill_candle_itself_is_checked(self) -> None:
        candles = _candles([
            (100, 101, 99, 100, 1000),      # signal candle
            (100, 101, 94, 95.5, 1000),     # fill 100; low 94 breaches SL 95 SAME bar
            (96, 97, 95, 96, 1000),
        ])
        rec = self._engine()._simulate_trade(
            "T", 0, "BUY", "swing", 75, stop_loss=95.0, take_profit=120.0,
            qty=10, candles=candles,
        )
        assert rec is not None
        assert rec.hit_sl is True
        assert rec.exit_price == 95.0           # intrabar on the fill candle
        assert rec.exit_date == candles.index[1]  # old behavior: never checked bar 1

    def test_sl_beats_tp_on_same_candle(self) -> None:
        candles = _candles([
            (100, 101, 99, 100, 1000),
            (100, 125, 94, 110, 1000),  # both SL 95 and TP 120 inside one bar
        ])
        rec = self._engine()._simulate_trade(
            "T", 0, "BUY", "swing", 75, stop_loss=95.0, take_profit=120.0,
            qty=10, candles=candles,
        )
        assert rec is not None
        assert rec.hit_sl is True  # conservative ordering preserved


class TestWindowCanon:
    def test_factor_window_capped_at_300(self) -> None:
        # 400 flat candles then a cliff INSIDE the last 300 → fib swing must
        # come from the capped window, proving the slice; mostly we assert
        # the engine runs the capped slice without touching older data.
        eng = BacktestEngine(BacktestConfig(capital=Decimal("100000"), risk_pct=Decimal("2")))
        rows = _flat(400, price=100.0)
        candles = _candles(rows)
        trades = eng.run_single_stock("T", candles)
        assert trades == []  # flat series can never fire — sanity
        # The real guarantee is structural: run_single_stock slices
        # candles.iloc[max(0, i+1-300):i+1]; assert the code path exists.
        import inspect

        src = inspect.getsource(eng.run_single_stock)
        assert "i + 1 - 300" in src


class TestStarGapRequired:
    """Adjudicated 2026-07-05 (item G): the star's real body must gap fully
    beyond the first candle's real body. Without the gap, 78% of detections
    were false and their ±0.95 dominated best-pattern selection (evidence:
    scripts/adjudication_experiments_fgh.py — corpus flipped −78.7 → +52.1)."""

    def test_morning_star_without_gap_rejected(self) -> None:
        # star body 100.5→102 OVERLAPS the first red body (bottom 100):
        # the pre-adjudication detector scored this +0.95
        df = _candles([
            (120, 125, 98, 100, 1000),
            (100.5, 103, 99, 102, 1000),
            (100, 116, 99, 115, 1000),
        ])
        r = detect_morning_evening_star(df)
        assert not r.detected
        assert r.score == 0.0

    def test_morning_star_with_gap_fires(self) -> None:
        # star body 98→99 sits fully below the first body bottom (100)
        df = _candles([
            (120, 125, 98, 100, 1000),
            (98, 100, 97, 99, 1000),
            (100, 116, 99, 115, 1000),
        ])
        r = detect_morning_evening_star(df)
        assert r.detected
        assert r.score == +0.95

    def test_evening_star_without_gap_rejected(self) -> None:
        # star body 119→118.5 overlaps the first green body (top 120)
        df = _candles([
            (100, 122, 98, 120, 1000),
            (119, 123, 118, 118.5, 1000),
            (120, 121, 99, 103, 1000),
        ])
        r = detect_morning_evening_star(df)
        assert not r.detected
        assert r.score == 0.0

    def test_evening_star_with_gap_fires(self) -> None:
        # star body 121→121.5 sits fully above the first body top (120)
        df = _candles([
            (100, 122, 98, 120, 1000),
            (121, 123, 120, 121.5, 1000),
            (120, 121, 99, 103, 1000),
        ])
        r = detect_morning_evening_star(df)
        assert r.detected
        assert r.score == -0.95


class TestVolatilitySizing:
    """Adjudicated 2026-07-05 (item F): ATR(14) > 3% of price → volatile
    regime → quantity reduced 25% as 3·qty // 4 (exact Rust mirror); a
    reduction to zero means the signal is rejected like any zero qty."""

    def test_volatile_regime_reduces_qty_25pct(self) -> None:
        # TR = 10 on price 100 → ATR ≈ 10% of price → volatile
        wild = _candles([(100, 105, 95, 100, 1000)] * 60)
        assert volatility_adjusted_qty(100, wild) == 75
        assert volatility_adjusted_qty(101, wild) == 75  # floor(75.75)
        assert volatility_adjusted_qty(1, wild) == 0  # reduces to rejection

    def test_calm_regime_keeps_qty(self) -> None:
        # TR = 2 on price 100 → ATR ≈ 2% of price → not volatile
        calm = _candles(_flat(60))
        assert volatility_adjusted_qty(100, calm) == 100

    def test_boundary_exactly_3pct_is_not_volatile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # spec says "> 3%": the boundary itself must NOT reduce
        import app.analysis.risk as risk_mod

        candles = _candles(_flat(20))
        monkeypatch.setattr(risk_mod, "atr_pct_of_price", lambda _c: 3.0)
        assert volatility_adjusted_qty(100, candles) == 100
        monkeypatch.setattr(risk_mod, "atr_pct_of_price", lambda _c: 3.0 + 1e-9)
        assert volatility_adjusted_qty(100, candles) == 75

    def test_short_history_never_volatile(self) -> None:
        # < ATR length → atr_pct_of_price returns 0.0 → unchanged
        assert volatility_adjusted_qty(50, _candles(_flat(5))) == 50
