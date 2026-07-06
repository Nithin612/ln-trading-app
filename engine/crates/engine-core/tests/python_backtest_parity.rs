//! Backtest parity: Rust run_single_stock vs the UPDATED (adjudicated)
//! Python BacktestEngine — 6 stocks × ~2.5y, EXACT trade-list equality:
//! same fills, same exits, same quantities, same pnl (1e-12 f64).
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use engine_core::backtest::{run_single_stock, BacktestParams};
use engine_core::risk::{money_from_str, Side};
use engine_core::types::Bar;
use serde::Deserialize;

#[derive(Deserialize)]
struct RawBar {
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: f64,
}

#[derive(Deserialize)]
struct PyTrade {
    fill_idx: usize,
    exit_idx: usize,
    direction: String,
    confidence: i32,
    entry: f64,
    sl: f64,
    tp: f64,
    qty: i64,
    exit_price: f64,
    pnl_pct: f64,
    hit_sl: bool,
    hit_target: bool,
}

#[derive(Deserialize)]
struct Case {
    symbol: String,
    bars: Vec<RawBar>,
    trades: Vec<PyTrade>,
}

#[derive(Deserialize)]
struct Fixture {
    cases: Vec<Case>,
}

#[test]
fn trade_lists_match_python_exactly() {
    let raw = include_str!("fixtures/python_backtest_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    let params = BacktestParams {
        capital: money_from_str("500000").expect("capital"),
        risk_pct: money_from_str("2").expect("risk"),
        min_confidence: 70,
        weight_multipliers: Vec::new(),
        tp_rule: None,
    };

    let mut total = 0usize;
    for case in &fx.cases {
        let bars: Vec<Bar> = case
            .bars
            .iter()
            .map(|b| Bar {
                open: b.open,
                high: b.high,
                low: b.low,
                close: b.close,
                volume: b.volume,
            })
            .collect();

        let got = run_single_stock(&bars, "1d", &params);
        assert_eq!(
            got.len(),
            case.trades.len(),
            "{}: trade count {} vs {}",
            case.symbol,
            got.len(),
            case.trades.len()
        );

        for (g, w) in got.iter().zip(case.trades.iter()) {
            let dir = if g.side == Side::Buy { "BUY" } else { "SELL" };
            assert_eq!(g.fill_idx, w.fill_idx, "{} fill_idx", case.symbol);
            assert_eq!(
                g.exit_idx, w.exit_idx,
                "{} exit_idx @fill {}",
                case.symbol, g.fill_idx
            );
            assert_eq!(
                dir, w.direction,
                "{} direction @{}",
                case.symbol, g.fill_idx
            );
            assert_eq!(
                g.confidence_pct, w.confidence,
                "{} conf @{}",
                case.symbol, g.fill_idx
            );
            assert_eq!(g.qty, w.qty, "{} qty @{}", case.symbol, g.fill_idx);
            for (name, a, b) in [
                ("entry", g.entry, w.entry),
                ("sl", g.stop_loss, w.sl),
                ("tp", g.take_profit, w.tp),
                ("exit", g.exit_price, w.exit_price),
            ] {
                assert!(
                    (a - b).abs() <= 1e-9,
                    "{} {} @{}: {} vs {}",
                    case.symbol,
                    name,
                    g.fill_idx,
                    a,
                    b
                );
            }
            assert!(
                (g.pnl_pct - w.pnl_pct).abs() <= 1e-12,
                "{} pnl @{}: {} vs {}",
                case.symbol,
                g.fill_idx,
                g.pnl_pct,
                w.pnl_pct
            );
            assert_eq!((g.hit_sl, g.hit_target), (w.hit_sl, w.hit_target));
            total += 1;
        }
    }
    assert!(total >= 100, "expected ≥100 trades, got {total}");
}
