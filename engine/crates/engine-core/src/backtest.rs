//! Backtest engine — faithful port of backend/app/backtest/engine.py at
//! the ADJUDICATED canon (2026-07-04): last-≤300 window, pivot swing-SL
//! (n=5) with degenerate/wrong-side rejection, honest fills (gap-through
//! exits at the OPEN, fill candle checked intrabar, SL before TP).
//!
//! Anti-look-ahead: factors computed on the window ending at candle i;
//! the trade fills at the OPEN of candle i+1. Money via risk.rs (i64·1e-4,
//! Decimal-parity conversions); pnl_pct in f64 exactly like Python.

use rayon::prelude::*;

use crate::confluence::{run_all_factors, score_from_factors, Direction, FlowInputs};
use crate::factors::Factor;
use crate::pivots::{swing_high_indices, swing_low_indices};
use crate::risk::{classify, compute_levels, compute_quantity, money_from_f64, Money, Side};
use crate::types::Bar;

pub const WINDOW_CANON: usize = 300;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Trade {
    pub fill_idx: usize,
    pub exit_idx: usize,
    pub side: Side,
    pub confidence_pct: i32,
    pub entry: f64,
    pub stop_loss: f64,
    pub take_profit: f64,
    pub qty: i64,
    pub exit_price: f64,
    pub pnl_pct: f64,
    pub hit_sl: bool,
    pub hit_target: bool,
}

#[derive(Debug, Clone, Default)]
pub struct BacktestParams {
    /// Whole-percent risk scaled 1e-4 (2% == 20_000).
    pub capital: Money,
    pub risk_pct: Money,
    pub min_confidence: i32,
    /// (group, multiplier) pairs — Python apply_weight_multipliers.
    pub weight_multipliers: Vec<(String, f64)>,
}

fn apply_weight_multipliers(factors: &mut [Factor], mults: &[(String, f64)]) {
    if mults.is_empty() {
        return;
    }
    for f in factors.iter_mut() {
        if let Some((_, m)) = mults.iter().find(|(g, _)| g == f.group) {
            if *m != 1.0 {
                f.weight *= m;
            }
        }
    }
}

/// Pivot swing levels on the window (n=5) — mirrors dow.swing_levels:
/// price via Decimal(str(f64)) equivalence.
fn window_swings(window: &[Bar]) -> (Option<Money>, Option<Money>) {
    const N: usize = 5;
    if window.len() < N * 2 + 1 {
        return (None, None);
    }
    let lows: Vec<f64> = window.iter().map(|b| b.low).collect();
    let highs: Vec<f64> = window.iter().map(|b| b.high).collect();
    let lo = swing_low_indices(&lows, N)
        .last()
        .and_then(|&i| lows.get(i))
        .and_then(|&p| money_from_f64(p));
    let hi = swing_high_indices(&highs, N)
        .last()
        .and_then(|&i| highs.get(i))
        .and_then(|&p| money_from_f64(p));
    (lo, hi)
}

#[inline]
fn money_to_f64(m: Money) -> f64 {
    m as f64 / 10_000.0
}

/// Everything decided about an order before simulation.
#[derive(Clone, Copy)]
struct PlannedOrder {
    side: Side,
    confidence_pct: i32,
    entry: Money,
    stop_loss: Money,
    take_profit: Money,
    qty: i64,
}

/// Honest-fill walk from the fill candle to the end of data.
fn simulate_trade(bars: &[Bar], fill_idx: usize, order: PlannedOrder) -> Option<Trade> {
    let PlannedOrder {
        side,
        confidence_pct,
        qty,
        ..
    } = order;
    let entry = money_to_f64(order.entry);
    let stop_loss = money_to_f64(order.stop_loss);
    let take_profit = money_to_f64(order.take_profit);
    let buy = side == Side::Buy;
    let sign = if buy { 1.0 } else { -1.0 };

    let mk = |exit_idx: usize, price: f64, sl: bool, tp: bool| Trade {
        fill_idx,
        exit_idx,
        side,
        confidence_pct,
        entry,
        stop_loss,
        take_profit,
        qty,
        exit_price: price,
        pnl_pct: sign * (price - entry) / entry * 100.0,
        hit_sl: sl,
        hit_target: tp,
    };

    for (off, c) in bars.get(fill_idx..)?.iter().enumerate() {
        let i = fill_idx + off;
        if i > fill_idx {
            let sl_gap = if buy {
                c.open <= stop_loss
            } else {
                c.open >= stop_loss
            };
            let tp_gap = if buy {
                c.open >= take_profit
            } else {
                c.open <= take_profit
            };
            if sl_gap {
                return Some(mk(i, c.open, true, false));
            }
            if tp_gap {
                return Some(mk(i, c.open, false, true));
            }
        }
        let hit_sl = if buy {
            c.low <= stop_loss
        } else {
            c.high >= stop_loss
        };
        let hit_tp = if buy {
            c.high >= take_profit
        } else {
            c.low <= take_profit
        };
        if hit_sl {
            return Some(mk(i, stop_loss, true, false));
        }
        if hit_tp {
            return Some(mk(i, take_profit, false, true));
        }
    }

    let last_idx = bars.len().checked_sub(1)?;
    let last_close = bars.last()?.close;
    Some(mk(last_idx, last_close, false, false))
}

/// Backtest one stock (Python run_single_stock at the adjudicated canon).
pub fn run_single_stock(bars: &[Bar], timeframe: &str, params: &BacktestParams) -> Vec<Trade> {
    let mut trades = Vec::new();
    if bars.len() < 60 {
        return trades;
    }

    for i in 50..bars.len() - 1 {
        let start = (i + 1).saturating_sub(WINDOW_CANON);
        let Some(window) = bars.get(start..=i) else {
            continue;
        };

        let mut factors = run_all_factors(window, timeframe, FlowInputs::default());
        apply_weight_multipliers(&mut factors, &params.weight_multipliers);
        let Some(outcome) = score_from_factors(&factors, window, params.min_confidence) else {
            continue;
        };

        let classification = classify(timeframe, outcome.is_multibagger);
        let Some(next_open) = bars.get(i + 1).map(|b| b.open) else {
            continue;
        };
        let Some(entry) = money_from_f64(next_open) else {
            continue;
        };

        let (swing_low, swing_high) = window_swings(window);
        let side = match outcome.direction {
            Direction::Buy => Side::Buy,
            Direction::Sell => Side::Sell,
        };
        let Some((sl, tp)) = compute_levels(
            side,
            classification,
            entry,
            if side == Side::Buy { swing_low } else { None },
            if side == Side::Sell { swing_high } else { None },
            None,
        ) else {
            continue;
        };
        // Degenerate/wrong-side SL rejection (adjudicated item C)
        if side == Side::Buy && sl >= entry {
            continue;
        }
        if side == Side::Sell && sl <= entry {
            continue;
        }
        let Some(qty) = compute_quantity(params.capital, params.risk_pct, entry, sl) else {
            continue;
        };
        if qty == 0 {
            continue;
        }

        let order = PlannedOrder {
            side,
            confidence_pct: outcome.confidence_pct,
            entry,
            stop_loss: sl,
            take_profit: tp,
            qty,
        };
        if let Some(trade) = simulate_trade(bars, i + 1, order) {
            trades.push(trade);
        }
    }
    trades
}

/// Rayon-parallel backtest across stocks; result order matches input order.
pub fn run_universe(
    stocks: &[(String, Vec<Bar>)],
    timeframe: &str,
    params: &BacktestParams,
) -> Vec<(String, Vec<Trade>)> {
    stocks
        .par_iter()
        .map(|(sym, bars)| (sym.clone(), run_single_stock(bars, timeframe, params)))
        .collect()
}
