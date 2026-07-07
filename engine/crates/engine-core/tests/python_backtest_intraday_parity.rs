//! Intraday backtest parity (Phase 2 slice 8c): Rust vs the frozen Python
//! oracle on REAL backfilled 5m/15m bars with session_last_bar flags —
//! EXACT trade-list equality (fills, exits, quantities, pnl at 1e-12).
//! The fixture pins the corpus (QA manifest 2026-07-07) verbatim; only
//! expectations regenerate via scripts/generate_engine_fixtures.py.
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
    timeframe: String,
    bars: Vec<RawBar>,
    session_last: Vec<bool>,
    trades: Vec<PyTrade>,
}

#[derive(Deserialize)]
struct Meta {
    capital: String,
    risk_pct: String,
}

#[derive(Deserialize)]
struct Fixture {
    #[serde(rename = "_meta")]
    meta: Meta,
    cases: Vec<Case>,
}

#[test]
fn intraday_trade_lists_match_python_exactly() {
    let raw = include_str!("fixtures/python_backtest_intraday_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    let params = BacktestParams {
        capital: money_from_str(&fx.meta.capital).expect("capital"),
        risk_pct: money_from_str(&fx.meta.risk_pct).expect("risk"),
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
        let got = run_single_stock(&bars, &case.timeframe, &params, Some(&case.session_last));
        let tag = format!("{}/{}", case.symbol, case.timeframe);
        assert_eq!(got.len(), case.trades.len(), "{tag}: trade count");
        for (r, p) in got.iter().zip(&case.trades) {
            assert_eq!(r.fill_idx, p.fill_idx, "{tag}: fill idx");
            assert_eq!(r.exit_idx, p.exit_idx, "{tag}: exit idx");
            let side = if p.direction == "BUY" {
                Side::Buy
            } else {
                Side::Sell
            };
            assert_eq!(r.side, side, "{tag}: side");
            assert_eq!(r.confidence_pct, p.confidence, "{tag}: confidence");
            assert_eq!(r.qty, p.qty, "{tag}@{}: qty", p.fill_idx);
            assert!((r.entry - p.entry).abs() <= 1e-9, "{tag}: entry");
            assert!((r.stop_loss - p.sl).abs() <= 1e-9, "{tag}: sl");
            assert!((r.take_profit - p.tp).abs() <= 1e-9, "{tag}: tp");
            assert!((r.exit_price - p.exit_price).abs() <= 1e-9, "{tag}: exit");
            assert!((r.pnl_pct - p.pnl_pct).abs() <= 1e-12, "{tag}: pnl");
            assert_eq!(
                (r.hit_sl, r.hit_target),
                (p.hit_sl, p.hit_target),
                "{tag}: flags"
            );
            total += 1;
        }
    }
    assert!(
        total >= 80,
        "only {total} intraday trades compared — fixture too thin"
    );
}

#[test]
fn intraday_trades_never_span_sessions() {
    // Self-consistency of the ORACLE itself: with flags on, every trade's
    // [fill, exit] must sit inside one session (no flagged bar strictly
    // before the exit bar within the trade's span).
    let raw = include_str!("fixtures/python_backtest_intraday_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    for case in &fx.cases {
        for t in &case.trades {
            let crossed = (t.fill_idx..t.exit_idx)
                .any(|i| case.session_last.get(i).copied().unwrap_or(false));
            assert!(
                !crossed,
                "{}/{}: trade {}..{} spans a session boundary",
                case.symbol, case.timeframe, t.fill_idx, t.exit_idx
            );
        }
    }
}
