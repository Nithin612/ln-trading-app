"""Trade-list metric aggregation (Phase 2 slice 8b).

Extracted from BacktestEngine.run so the walk-forward runner and the
engine share ONE implementation — with a fixed ordering canon.

ORDERING CANON: the equity curve (and therefore max drawdown) compounds
trades sorted by (entry_date, stock). The pre-extraction engine compounded
them in dict-insertion order — stock-grouped, not time-ordered — which
made max-DD physically meaningless across stocks and dependent on universe
ordering. Win rate / averages / Sharpe / Sortino are order-independent and
unchanged. Recorded in docs/PERFORMANCE.md: equity/DD values before this
fix are not comparable.
"""

from __future__ import annotations

from app.backtest.engine import (
    BacktestResult,
    TradeRecord,
    _compute_drawdown,
    _compute_sharpe,
    _compute_sortino,
)


def aggregate_trades(trades: list[TradeRecord]) -> BacktestResult:
    """Aggregate a trade list into a BacktestResult (canonical ordering)."""
    if not trades:
        return BacktestResult()

    ordered = sorted(trades, key=lambda t: (t.entry_date, t.stock))

    winning = [t for t in ordered if (t.pnl_pct or 0) > 0]
    losing = [t for t in ordered if (t.pnl_pct or 0) <= 0]
    pnl_list = [t.pnl_pct or 0.0 for t in ordered]

    total_pnl = sum(pnl_list)
    avg_pnl = total_pnl / len(ordered)
    win_rate = len(winning) / len(ordered) * 100

    rr_list = []
    for t in ordered:
        if t.entry_price and t.stop_loss and t.take_profit:
            risk = abs(t.entry_price - t.stop_loss)
            reward = abs(t.entry_price - t.take_profit)
            if risk > 0:
                rr_list.append(reward / risk)
    avg_rr = sum(rr_list) / len(rr_list) if rr_list else 0.0

    equity = [100.0]
    for p in pnl_list:
        equity.append(equity[-1] * (1 + p / 100))

    holding_days = []
    for t in ordered:
        if t.exit_date is not None and t.entry_date is not None:
            holding_days.append((t.exit_date - t.entry_date).days)
    avg_holding = sum(holding_days) / len(holding_days) if holding_days else 0.0

    return BacktestResult(
        total_trades=len(ordered),
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
        trades=ordered,
    )
