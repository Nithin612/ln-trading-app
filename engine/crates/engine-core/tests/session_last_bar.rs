//! session_last_bar axis (Phase 2 slice 8c) — semantics pinned against the
//! committed 1d oracle bars:
//!   1. None ≡ all-false flags (the extension is default-off);
//!   2. a flagged DECISION bar mints nothing (all-flagged ⇒ zero trades);
//!   3. an open trade force-exits at a flagged bar's CLOSE, after that
//!      bar's SL-before-TP checks.
#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::indexing_slicing
)]

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
struct Case {
    symbol: String,
    bars: Vec<RawBar>,
}

#[derive(Deserialize)]
struct Fixture {
    cases: Vec<Case>,
}

fn load_bars() -> Vec<(String, Vec<Bar>)> {
    let raw = include_str!("fixtures/python_backtest_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    fx.cases
        .into_iter()
        .map(|c| {
            let bars = c
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
            (c.symbol, bars)
        })
        .collect()
}

fn params() -> BacktestParams {
    BacktestParams {
        capital: money_from_str("500000").expect("capital"),
        risk_pct: money_from_str("2").expect("risk"),
        min_confidence: 70,
        weight_multipliers: Vec::new(),
        tp_rule: None,
    }
}

#[test]
fn all_false_flags_are_identical_to_none() {
    let p = params();
    let mut compared = 0usize;
    for (sym, bars) in load_bars() {
        let baseline = run_single_stock(&bars, "1d", &p, None);
        let flags = vec![false; bars.len()];
        let flagged = run_single_stock(&bars, "1d", &p, Some(&flags));
        assert_eq!(baseline, flagged, "{sym}: all-false flags changed trades");
        compared += baseline.len();
    }
    assert!(
        compared >= 50,
        "only {compared} trades compared — fixture too thin"
    );
}

#[test]
fn flagged_decision_bars_never_mint() {
    let p = params();
    let mut suppressed = 0usize;
    for (sym, bars) in load_bars() {
        let flags = vec![true; bars.len()];
        let trades = run_single_stock(&bars, "1d", &p, Some(&flags));
        assert!(
            trades.is_empty(),
            "{sym}: all-flagged minted {}",
            trades.len()
        );
        suppressed += run_single_stock(&bars, "1d", &p, None).len();
    }
    assert!(suppressed > 0, "baseline minted nothing — vacuous test");
}

#[test]
fn open_trade_exits_at_flagged_bar_close() {
    let p = params();
    let mut exercised = 0usize;
    for (sym, bars) in load_bars() {
        let baseline = run_single_stock(&bars, "1d", &p, None);
        // A multi-bar trade whose fill bar is NOT its own exit: flagging the
        // fill bar k only (a) kills trades whose DECISION bar is k, and
        // (b) must close THIS trade at k's close (no SL/TP hit at k in the
        // baseline, else it would have exited there).
        let Some(t) = baseline.iter().find(|t| t.exit_idx > t.fill_idx) else {
            continue;
        };
        let k = t.fill_idx;
        let mut flags = vec![false; bars.len()];
        flags[k] = true;
        let flagged = run_single_stock(&bars, "1d", &p, Some(&flags));
        let got = flagged
            .iter()
            .find(|x| x.fill_idx == k && x.side == t.side && x.entry == t.entry)
            .unwrap_or_else(|| panic!("{sym}: trade at fill {k} vanished"));
        assert_eq!(got.exit_idx, k, "{sym}: exit index");
        assert_eq!(
            got.exit_price, bars[k].close,
            "{sym}: exit at flagged close"
        );
        assert!(
            !got.hit_sl && !got.hit_target,
            "{sym}: session exit is neither SL nor TP"
        );
        let sign = if t.side == Side::Buy { 1.0 } else { -1.0 };
        let want_pnl = sign * (bars[k].close - t.entry) / t.entry * 100.0;
        assert!(
            (got.pnl_pct - want_pnl).abs() < 1e-12,
            "{sym}: session-exit pnl"
        );
        exercised += 1;
    }
    assert!(exercised >= 3, "only {exercised} close-outs exercised");
}

#[test]
fn stop_loss_beats_session_exit_on_the_same_bar() {
    let p = params();
    let mut exercised = 0usize;
    for (sym, bars) in load_bars() {
        let baseline = run_single_stock(&bars, "1d", &p, None);
        // Flag the first baseline SL-exit bar (one per symbol keeps the
        // test fast): the trade must STILL exit at the stop
        // (SL-before-session ordering), not at the close.
        if let Some(t) = baseline
            .iter()
            .find(|t| t.hit_sl && t.exit_idx > t.fill_idx)
        {
            let mut flags = vec![false; bars.len()];
            flags[t.exit_idx] = true;
            let flagged = run_single_stock(&bars, "1d", &p, Some(&flags));
            if let Some(got) = flagged
                .iter()
                .find(|x| x.fill_idx == t.fill_idx && x.entry == t.entry && x.side == t.side)
            {
                assert_eq!(got.exit_idx, t.exit_idx, "{sym}: SL bar");
                assert!(got.hit_sl, "{sym}: SL must beat the session close-out");
                assert_eq!(got.exit_price, t.exit_price, "{sym}: exits at the stop");
                exercised += 1;
            }
        }
    }
    assert!(
        exercised >= 2,
        "only {exercised} SL-vs-session races exercised"
    );
}
