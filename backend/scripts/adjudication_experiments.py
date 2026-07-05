"""Adjudication evidence pack (Phase 1, UPGRADE_PLAN.md).

Five places where code drifted from SIGNAL_ENGINE.md need USER decisions
before golden fixtures are generated. This script measures the backtest
impact of aligning each one, WITHOUT touching production code — variants
live here as monkeypatches/subclasses and die after the decision.

  A  volume direction-match   spec §2.3: "only counts if direction matches"
  B  RSI ±0.4 bands           not in spec §2.3
  C  SL canon                 backtest 20-bar min/max vs live pivot N=5
  D  window canon             growing window (backtest) vs last-300 (live)
  E  fill realism             gap-through-SL + fill-candle SL/TP checks

Run: uv run python scripts/adjudication_experiments.py
Corpus: 2y × Nifty50 daily from ohlcv_1d (backfill first).
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.analysis.confluence import (  # noqa: E402
    run_all_factors,
    score_from_factors,
)
from app.analysis.risk import compute_levels, compute_quantity  # noqa: E402
from app.backtest.engine import (  # noqa: E402
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    TradeRecord,
    apply_weight_multipliers,
)
from app.services.signal_service import _swing_levels  # noqa: E402
from app.signals.classifier import classify_signal  # noqa: E402
from bench_baseline import load_universe  # noqa: E402  (same scripts dir)

CFG = BacktestConfig(
    timeframe="1d", universe="NIFTY50",
    capital=Decimal("500000"), risk_pct=Decimal("2"), min_confidence=70,
)


# ── Variant A: volume only counts when it matches the rest ──────────────────

def score_with_directional_volume(factors, candles, min_confidence=70):  # noqa: ANN001, ANN201
    """Spec §2.3 weights table: volume 'only counts if direction matches'."""
    rest = sum(f.weight * f.score for f in factors if f.name != "VOLUME")
    adjusted = []
    for f in factors:
        if f.name == "VOLUME" and f.score > 0:
            if rest > 0:
                new_score = +0.5
            elif rest < 0:
                new_score = -0.5
            else:
                new_score = 0.0
            f = type(f)(f.name, f.weight, new_score, f.explanation, f.tags)
        adjusted.append(f)
    return score_from_factors(adjusted, candles, min_confidence)


# ── Variant B: RSI level factor without the off-spec ±0.4 bands ─────────────

def make_rsi_level_no_bands():  # noqa: ANN201
    import app.analysis.indicators.rsi as rsi_mod
    original = rsi_mod.rsi_level_factor

    def patched(candles):  # noqa: ANN001, ANN202
        result = original(candles)
        if abs(result.score) == 0.4:  # exactly the off-spec band scores
            return type(result)(result.name, result.weight, 0.0,
                                result.explanation + " [band zeroed: off-spec]")
        return result

    return patched


# ── Variant C/E: engine subclass with pivot-SL and/or realistic fills ────────

class VariantEngine(BacktestEngine):
    """run_single_stock copied from BacktestEngine with two switchable
    changes, clearly marked. Throwaway experiment code — the adjudicated
    behavior gets implemented properly (with tests) after the decision."""

    def __init__(self, config, pivot_sl=False, realistic_fills=False,  # noqa: ANN001
                 directional_volume=False, rsi_no_bands=False) -> None:
        super().__init__(config)
        self.pivot_sl = pivot_sl
        self.realistic_fills = realistic_fills
        self.directional_volume = directional_volume
        self.rsi_no_bands = rsi_no_bands

    def run_single_stock(self, stock: str, candles: pd.DataFrame) -> list[TradeRecord]:  # noqa: C901
        trades: list[TradeRecord] = []
        if len(candles) < 60:
            return trades

        scorer = score_with_directional_volume if self.directional_volume else score_from_factors
        rsi_patch = make_rsi_level_no_bands() if self.rsi_no_bands else None

        for i in range(50, len(candles) - 1):
            window = candles.iloc[: i + 1]

            cm = contextlib.ExitStack()
            with cm:
                if rsi_patch is not None:
                    import unittest.mock as um

                    import app.analysis.confluence as conf_mod
                    cm.enter_context(
                        um.patch.object(conf_mod, "rsi_level_factor", rsi_patch)
                    )
                factors = run_all_factors(window, timeframe=self.config.timeframe)

            if self.config.weight_multipliers:
                factors = apply_weight_multipliers(factors, self.config.weight_multipliers)
            result = scorer(factors, window, self.config.min_confidence)
            if result is None:
                continue

            classification = classify_signal(
                self.config.timeframe, result.factors, result.is_multibagger
            )
            entry_price = Decimal(str(float(candles.iloc[i + 1]["open"])))

            if self.pivot_sl:
                # VARIANT C: live-parity swing levels (pivot N=5)
                swing_low, swing_high = _swing_levels(window)
            else:
                swing_low = Decimal(str(float(window["low"].iloc[-20:].min())))
                swing_high = Decimal(str(float(window["high"].iloc[-20:].max())))

            levels = compute_levels(
                direction=result.direction,
                classification=classification,
                entry=entry_price,
                swing_low=swing_low if result.direction == "BUY" else None,
                swing_high=swing_high if result.direction == "SELL" else None,
            )
            if levels is None:
                continue
            stop_loss, take_profit = levels
            # Experiment guard: pivot swings can coincide with (or cross) the
            # next open — degenerate/wrong-side SLs are skipped, mirroring the
            # reject-don't-clamp rule. (Latent in prod too: compute_quantity
            # abs()'s wrong-side SLs — flagged for quant-verifier.)
            if result.direction == "BUY" and stop_loss >= entry_price:
                continue
            if result.direction == "SELL" and stop_loss <= entry_price:
                continue
            qty = compute_quantity(
                self.config.capital, self.config.risk_pct, entry_price, stop_loss
            )
            if qty == 0:
                continue

            record = self._simulate_trade_variant(
                stock, candles, i + 1, result, classification,
                float(entry_price), float(stop_loss), float(take_profit), qty,
            )
            trades.append(record)
        return trades

    def _simulate_trade_variant(  # noqa: PLR0913
        self, stock, candles, fill_idx, result, classification,
        entry_price, stop_loss, take_profit, qty,
    ) -> TradeRecord:
        record = TradeRecord(
            stock=stock,
            direction=result.direction,
            classification=classification,
            confidence_pct=result.confidence_pct,
            entry_date=pd.Timestamp(candles.index[fill_idx]),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            qty=qty,
        )
        # VARIANT E: include the fill candle itself; exit at gap price.
        start = fill_idx if self.realistic_fills else fill_idx + 1
        buy = result.direction == "BUY"

        for i in range(start, len(candles)):
            c = candles.iloc[i]
            o, high, low = float(c["open"]), float(c["high"]), float(c["low"])

            if self.realistic_fills:
                sl_gap = o <= stop_loss if buy else o >= stop_loss
                tp_gap = o >= take_profit if buy else o <= take_profit
                # On the fill candle the entry IS the open: a same-bar gap
                # exit can't be better than open, so gap checks apply from
                # the next bar; intrabar checks apply from the fill bar.
                if i > fill_idx and sl_gap:
                    return self._exit(record, candles, i, o, sl=True)
                if i > fill_idx and tp_gap:
                    return self._exit(record, candles, i, o, sl=False)

            hit_sl = low <= stop_loss if buy else high >= stop_loss
            hit_tp = high >= take_profit if buy else low <= take_profit
            if hit_sl:
                return self._exit(record, candles, i, stop_loss, sl=True)
            if hit_tp:
                return self._exit(record, candles, i, take_profit, sl=False)

        last_close = float(candles.iloc[-1]["close"])
        record.exit_date = pd.Timestamp(candles.index[-1])
        record.exit_price = last_close
        sign = 1 if buy else -1
        record.pnl_pct = sign * (last_close - record.entry_price) / record.entry_price * 100
        return record

    def _exit(self, record, candles, i, price, sl):  # noqa: ANN001, ANN202, FBT002
        record.exit_date = pd.Timestamp(candles.index[i])
        record.exit_price = price
        record.hit_sl = sl
        record.hit_target = not sl
        sign = 1 if record.direction == "BUY" else -1
        record.pnl_pct = sign * (price - record.entry_price) / record.entry_price * 100
        return record


# ── Variant D: growing-window vs last-300 decision agreement ────────────────

def window_canon_experiment(frames: dict[str, pd.DataFrame], n_stocks=10, stride=5):  # noqa: ANN001, ANN201
    symbols = sorted(frames)[:n_stocks]
    evals = agree = flips_dir = flips_gate = 0
    conf_deltas: list[float] = []
    for sym in symbols:
        df = frames[sym]
        for i in range(320, len(df) - 1, stride):
            growing = df.iloc[: i + 1]
            fixed = growing.iloc[-300:]
            r_g = score_from_factors(run_all_factors(growing, "1d"), growing, 70)
            r_f = score_from_factors(run_all_factors(fixed, "1d"), fixed, 70)
            evals += 1
            if (r_g is None) != (r_f is None):
                flips_gate += 1
            elif r_g is not None and r_f is not None:
                if r_g.direction != r_f.direction:
                    flips_dir += 1
                else:
                    agree += 1
                    conf_deltas.append(abs(r_g.confidence_pct - r_f.confidence_pct))
            else:
                agree += 1
    return {
        "evals": evals,
        "agree_pct": 100.0 * agree / max(evals, 1),
        "gate_flips": flips_gate,
        "direction_flips": flips_dir,
        "mean_conf_delta": (sum(conf_deltas) / len(conf_deltas)) if conf_deltas else 0.0,
        "max_conf_delta": max(conf_deltas, default=0.0),
    }


def fmt_row(name: str, r: BacktestResult, seconds: float) -> str:
    return (
        f"| {name:<22} | {r.total_trades:>6} | {r.win_rate_pct:>5.1f} | "
        f"{r.avg_pnl_pct:>7.2f} | {r.total_pnl_pct:>8.1f} | {r.sharpe:>6.2f} | "
        f"{r.max_drawdown_pct:>6.1f} | {seconds/60:>5.1f}m |"
    )


def main() -> int:
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
    two_years_ago = datetime.now(UTC) - timedelta(days=365 * 2 + 30)
    frames = asyncio.run(load_universe(True, min_rows=200, since=two_years_ago))
    print(f"corpus: {len(frames)} Nifty50 stocks, 2y daily\n")
    if not frames:
        print("NO DATA — run scripts/backfill_eod.py first")
        return 2

    variants: list[tuple[str, dict[str, bool]]] = [
        ("BASELINE (as-is)", {}),
        ("A volume-directional", {"directional_volume": True}),
        ("B rsi-no-bands", {"rsi_no_bands": True}),
        ("C pivot-SL", {"pivot_sl": True}),
        ("E realistic-fills", {"realistic_fills": True}),
        ("A+B+C+E combined", {"directional_volume": True, "rsi_no_bands": True,
                              "pivot_sl": True, "realistic_fills": True}),
    ]

    print(
        "| variant                | trades | win%  | avgPnL% "
        "| totPnL%  | sharpe | maxDD% | time  |"
    )
    print("|------------------------|--------|-------|---------|----------|--------|--------|-------|")
    for name, flags in variants:
        if only is not None and name.split(" ")[0] not in only:
            continue
        t0 = time.perf_counter()
        result = VariantEngine(CFG, **flags).run(frames)
        print(fmt_row(name, result, time.perf_counter() - t0), flush=True)

    print("\nD window canon (growing vs last-300), 10 stocks, stride 5:")
    d = window_canon_experiment(frames)
    print(
        f"  evals={d['evals']}  agreement={d['agree_pct']:.1f}%  "
        f"gate flips={d['gate_flips']}  direction flips={d['direction_flips']}  "
        f"confidence Δ mean={d['mean_conf_delta']:.2f} max={d['max_conf_delta']:.0f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
