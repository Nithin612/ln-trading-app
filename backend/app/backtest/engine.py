"""Backtest harness — offline signal engine replay on historical OHLCV data.

Design principles (anti-look-ahead):
  - Compute factors on candle N, generate signal valid from candle N+1 open.
  - A signal is filled at the OPEN of candle N+1.
  - TP/SL checked on candles after the fill candle.

Usage:
    from app.backtest.engine import BacktestEngine, BacktestConfig
    cfg = BacktestConfig(period_years=2, universe="NIFTY50")
    engine = BacktestEngine(cfg)
    result = engine.run(candles_by_stock)
"""

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from app.analysis.confluence import run_all_factors, score_from_factors
from app.analysis.risk import compute_levels, compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import swing_levels
from app.analysis.types import FactorResult  # noqa: F401 — re-exported for callers
from app.signals.classifier import classify_signal

# Maps factor tag/name groups to the keys users can tune.
# Pattern matching: if any tag is in the set, that group applies.
# Name matching: exact factor name used as fallback.
_GROUP_TAGS: dict[str, set[str]] = {
    "pattern":       {"pattern"},
    "trend":         {"trend"},
    "momentum":      {"momentum"},
    "volume":        {"volume"},
    "structure":     {"structure"},
    "institutional": {"institutional"},
}

_GROUP_NAMES: dict[str, set[str]] = {
    "trend":         {"DOW_TREND", "EMA_CROSS", "PRICE_VS_EMA"},
    "momentum":      {"RSI_LEVEL", "RSI_DIVERGENCE", "MACD_CROSS", "MACD_HISTOGRAM"},
    "volume":        {"VOLUME", "BBANDS"},
    "structure":     {"SR_ZONE", "FIBONACCI", "ADX"},
    "institutional": {"FII_DII", "MULTIBAGGER_EMA"},
}


def _factor_group(factor: FactorResult) -> str | None:
    """Return the weight-group key for a factor, or None if uncategorised."""
    for group, tag_set in _GROUP_TAGS.items():
        if any(t in tag_set for t in factor.tags):
            return group
    for group, name_set in _GROUP_NAMES.items():
        if factor.name in name_set:
            return group
    return None


def apply_weight_multipliers(
    factors: list[FactorResult],
    multipliers: dict[str, float],
) -> list[FactorResult]:
    """Return a new list of FactorResult with weights scaled by group multipliers.

    Factors not matched to any group are returned unchanged.
    """
    if not multipliers:
        return factors
    result = []
    for f in factors:
        group = _factor_group(f)
        mult = multipliers.get(group, 1.0) if group else 1.0
        if mult == 1.0:
            result.append(f)
        else:
            result.append(
                FactorResult(
                    name=f.name,
                    weight=f.weight * mult,
                    score=f.score,
                    explanation=f.explanation,
                    tags=f.tags,
                )
            )
    return result


@dataclass
class BacktestConfig:
    period_years: int = 2
    universe: str = "NIFTY50"
    timeframe: str = "1d"
    capital: Decimal = Decimal("100000")
    risk_pct: Decimal = Decimal("2")
    min_confidence: int = 70
    weight_multipliers: dict[str, float] = field(default_factory=dict)


@dataclass
class TradeRecord:
    stock: str
    direction: str
    classification: str
    confidence_pct: int
    entry_date: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    qty: int
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    pnl_pct: float | None = None
    hit_target: bool = False
    hit_sl: bool = False


@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_pct: float = 0.0
    avg_pnl_pct: float = 0.0
    win_rate_pct: float = 0.0
    avg_rr: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    avg_holding_days: float = 0.0
    equity_curve: list[float] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)


def _compute_drawdown(equity_curve: list[float]) -> float:
    """Maximum drawdown as percentage of peak equity."""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        max_dd = max(max_dd, dd)
    return max_dd


def _compute_sharpe(returns: list[float], risk_free: float = 6.0) -> float:
    """Annualised Sharpe ratio (Indian risk-free ~6%)."""
    if len(returns) < 2:
        return 0.0
    import statistics
    mean = statistics.mean(returns)
    std = statistics.stdev(returns)
    if std == 0:
        return 0.0
    daily_rf = risk_free / 252 / 100
    return float((mean / 100 - daily_rf) / (std / 100) * (252 ** 0.5))


def _compute_sortino(returns: list[float], risk_free: float = 6.0) -> float:
    """Annualised Sortino ratio."""
    if len(returns) < 2:
        return 0.0
    import statistics
    mean = statistics.mean(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0
    downside_std = statistics.stdev(downside) if len(downside) > 1 else abs(downside[0])
    if downside_std == 0:
        return 0.0
    daily_rf = risk_free / 252 / 100
    return float((mean / 100 - daily_rf) / (downside_std / 100) * (252 ** 0.5))


class BacktestEngine:
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def _simulate_trade(
        self,
        stock: str,
        signal_candle_idx: int,
        direction: str,
        classification: str,
        confidence_pct: int,
        stop_loss: float,
        take_profit: float,
        qty: int,
        candles: pd.DataFrame,
    ) -> TradeRecord | None:
        """Simulate a trade starting from candle N+1 after signal generation.

        Fills at open of N+1. Then walks forward checking SL/TP on each candle.
        """
        fill_idx = signal_candle_idx + 1
        if fill_idx >= len(candles):
            return None

        fill_candle = candles.iloc[fill_idx]
        entry_price = float(fill_candle["open"])
        raw_idx = candles.index[fill_idx]
        entry_date = raw_idx if hasattr(raw_idx, "to_pydatetime") else fill_idx

        record = TradeRecord(
            stock=stock,
            direction=direction,
            classification=classification,
            confidence_pct=confidence_pct,
            entry_date=pd.Timestamp(entry_date),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            qty=qty,
        )

        # Walk forward checking SL/TP — HONEST fills (adjudicated 2026-07-04):
        # the fill candle itself is checked intrabar, and gaps through a
        # level exit at the OPEN (the real executable price), not at the
        # level. SL checked before TP (conservative on both-hit candles).
        buy = direction == "BUY"

        def _exit(i: int, price: float, sl: bool) -> TradeRecord:
            record.exit_date = pd.Timestamp(candles.index[i])
            record.exit_price = price
            record.hit_sl = sl
            record.hit_target = not sl
            sign = 1 if buy else -1
            record.pnl_pct = sign * (price - entry_price) / entry_price * 100
            return record

        for i in range(fill_idx, len(candles)):
            c = candles.iloc[i]
            o, high, low = float(c["open"]), float(c["high"]), float(c["low"])

            # Gap exits apply from the bar AFTER the fill (on the fill bar
            # the entry IS the open, so a same-bar "gap" can't beat it).
            if i > fill_idx:
                sl_gap = o <= stop_loss if buy else o >= stop_loss
                tp_gap = o >= take_profit if buy else o <= take_profit
                if sl_gap:
                    return _exit(i, o, sl=True)
                if tp_gap:
                    return _exit(i, o, sl=False)

            hit_sl = low <= stop_loss if buy else high >= stop_loss
            hit_tp = high >= take_profit if buy else low <= take_profit
            if hit_sl:
                return _exit(i, stop_loss, sl=True)
            if hit_tp:
                return _exit(i, take_profit, sl=False)

        # Signal expired without hitting TP or SL — mark as break-even at last close
        last = candles.iloc[-1]
        last_close = float(last["close"])
        record.exit_date = pd.Timestamp(candles.index[-1])
        record.exit_price = last_close
        if direction == "BUY":
            record.pnl_pct = (last_close - entry_price) / entry_price * 100
        else:
            record.pnl_pct = (entry_price - last_close) / entry_price * 100
        return record

    def run_single_stock(self, stock: str, candles: pd.DataFrame) -> list[TradeRecord]:
        """Run backtest on one stock's full candle history."""
        trades: list[TradeRecord] = []
        # Need at least 60 candles for warm-up
        if len(candles) < 60:
            return trades

        for i in range(50, len(candles) - 1):
            # Window canon (adjudicated 2026-07-04): factors see exactly the
            # last ≤300 completed candles — identical to live evaluation.
            window = candles.iloc[max(0, i + 1 - 300) : i + 1]
            factors = run_all_factors(window, timeframe=self.config.timeframe)
            if self.config.weight_multipliers:
                factors = apply_weight_multipliers(factors, self.config.weight_multipliers)
            result = score_from_factors(factors, window, self.config.min_confidence)
            if result is None:
                continue

            classification = classify_signal(
                self.config.timeframe, result.factors, result.is_multibagger
            )
            entry_price = Decimal(str(float(candles.iloc[i + 1]["open"])))

            # SL canon (adjudicated 2026-07-04): the same pivot-based swing
            # levels live uses — the backtest must test what live does.
            swing_low, swing_high = swing_levels(window)

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
            # Pivot swings can coincide with (or cross) the next open —
            # degenerate/wrong-side SLs are rejected, never clamped.
            if result.direction == "BUY" and stop_loss >= entry_price:
                continue
            if result.direction == "SELL" and stop_loss <= entry_price:
                continue
            qty = compute_quantity(
                self.config.capital, self.config.risk_pct, entry_price, stop_loss
            )
            # Volatility regime (§4, adjudicated 2026-07-05): ATR(14) > 3% of
            # price on the decision window → size reduced 25%; zero rejects.
            qty = volatility_adjusted_qty(qty, window)
            if qty == 0:
                continue

            trade = self._simulate_trade(
                stock=stock,
                signal_candle_idx=i,
                direction=result.direction,
                classification=classification,
                confidence_pct=result.confidence_pct,
                stop_loss=float(stop_loss),
                take_profit=float(take_profit),
                qty=qty,
                candles=candles,
            )
            if trade is not None:
                trades.append(trade)

        return trades

    def run(self, candles_by_stock: dict[str, pd.DataFrame]) -> BacktestResult:
        """Run on all stocks and aggregate results."""
        all_trades: list[TradeRecord] = []
        for stock, candles in candles_by_stock.items():
            all_trades.extend(self.run_single_stock(stock, candles))

        if not all_trades:
            return BacktestResult()

        winning = [t for t in all_trades if (t.pnl_pct or 0) > 0]
        losing = [t for t in all_trades if (t.pnl_pct or 0) <= 0]
        pnl_list = [t.pnl_pct or 0.0 for t in all_trades]

        total_pnl = sum(pnl_list)
        avg_pnl = total_pnl / len(all_trades)
        win_rate = len(winning) / len(all_trades) * 100

        # Average R:R from hit-target trades
        rr_list = []
        for t in all_trades:
            if t.entry_price and t.stop_loss and t.take_profit:
                risk = abs(t.entry_price - t.stop_loss)
                reward = abs(t.entry_price - t.take_profit)
                if risk > 0:
                    rr_list.append(reward / risk)
        avg_rr = sum(rr_list) / len(rr_list) if rr_list else 0.0

        # Equity curve (cumulative PnL % starting at 100)
        equity = [100.0]
        for p in pnl_list:
            equity.append(equity[-1] * (1 + p / 100))

        # Holding days
        holding_days = []
        for t in all_trades:
            if t.exit_date and t.entry_date:
                days = (t.exit_date - t.entry_date).days
                holding_days.append(days)
        avg_holding = sum(holding_days) / len(holding_days) if holding_days else 0.0

        return BacktestResult(
            total_trades=len(all_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_pct=round(total_pnl, 3),
            avg_pnl_pct=round(avg_pnl, 3),
            win_rate_pct=round(win_rate, 2),
            avg_rr=round(avg_rr, 2),
            max_drawdown_pct=round(_compute_drawdown(equity), 3),
            sharpe=round(_compute_sharpe(pnl_list), 3),
            sortino=round(_compute_sortino(pnl_list), 3),
            avg_holding_days=round(avg_holding, 2),
            equity_curve=[round(v, 4) for v in equity],
            trades=all_trades,
        )
