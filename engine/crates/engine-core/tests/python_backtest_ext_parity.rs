//! Slice-8a axes parity: weight_multipliers + tp_rule vs the UPDATED
//! Python BacktestEngine — EXACT trade-list equality, joining bars from
//! the base backtest fixture by symbol (bars are not duplicated).
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::collections::HashMap;

use engine_core::backtest::{run_single_stock, BacktestParams};
use engine_core::risk::{money_from_str, Side, TpRule};
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
struct BaseCase {
    symbol: String,
    bars: Vec<RawBar>,
}

#[derive(Deserialize)]
struct BaseFixture {
    cases: Vec<BaseCase>,
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
struct ExtTpRule {
    kind: String,
    ratio: Option<String>,
    target_pct: Option<String>,
}

#[derive(Deserialize)]
struct ExtCase {
    symbol: String,
    variant: String,
    weight_multipliers: HashMap<String, f64>,
    tp_rule: Option<ExtTpRule>,
    trades: Vec<PyTrade>,
}

#[derive(Deserialize)]
struct ExtFixture {
    cases: Vec<ExtCase>,
}

fn parse_tp(rule: &Option<ExtTpRule>) -> Option<TpRule> {
    let r = rule.as_ref()?;
    match r.kind.as_str() {
        "rr" => Some(TpRule::Rr(
            money_from_str(r.ratio.as_ref().expect("ratio")).expect("ratio parses"),
        )),
        "flat_pct" => Some(TpRule::FlatPct(
            money_from_str(r.target_pct.as_ref().expect("target_pct")).expect("pct parses"),
        )),
        other => panic!("unknown tp_rule kind {other}"),
    }
}

#[test]
fn ext_axes_match_python_exactly() {
    let base: BaseFixture =
        serde_json::from_str(include_str!("fixtures/python_backtest_reference.json"))
            .expect("base fixture parses");
    let ext: ExtFixture =
        serde_json::from_str(include_str!("fixtures/python_backtest_ext_reference.json"))
            .expect("ext fixture parses");

    let bars_by_symbol: HashMap<&str, Vec<Bar>> = base
        .cases
        .iter()
        .map(|c| {
            (
                c.symbol.as_str(),
                c.bars
                    .iter()
                    .map(|b| Bar {
                        open: b.open,
                        high: b.high,
                        low: b.low,
                        close: b.close,
                        volume: b.volume,
                    })
                    .collect(),
            )
        })
        .collect();

    assert!(ext.cases.len() >= 18, "expected 3 variants x 6 stocks");
    let mut total = 0usize;
    for case in &ext.cases {
        let bars = bars_by_symbol
            .get(case.symbol.as_str())
            .unwrap_or_else(|| panic!("{} missing from base fixture", case.symbol));
        let params = BacktestParams {
            capital: money_from_str("500000").expect("capital"),
            risk_pct: money_from_str("2").expect("risk"),
            min_confidence: 70,
            weight_multipliers: case
                .weight_multipliers
                .iter()
                .map(|(k, v)| (k.clone(), *v))
                .collect(),
            tp_rule: parse_tp(&case.tp_rule),
        };
        let got = run_single_stock(bars, "1d", &params);
        assert_eq!(
            got.len(),
            case.trades.len(),
            "{}/{}: trade count {} vs {}",
            case.symbol,
            case.variant,
            got.len(),
            case.trades.len()
        );
        for (g, w) in got.iter().zip(case.trades.iter()) {
            let dir = if g.side == Side::Buy { "BUY" } else { "SELL" };
            let tag = format!("{}/{}@{}", case.symbol, case.variant, g.fill_idx);
            assert_eq!(g.fill_idx, w.fill_idx, "{tag} fill_idx");
            assert_eq!(g.exit_idx, w.exit_idx, "{tag} exit_idx");
            assert_eq!(dir, w.direction, "{tag} direction");
            assert_eq!(g.confidence_pct, w.confidence, "{tag} conf");
            assert_eq!(g.qty, w.qty, "{tag} qty");
            for (name, a, b) in [
                ("entry", g.entry, w.entry),
                ("sl", g.stop_loss, w.sl),
                ("tp", g.take_profit, w.tp),
                ("exit", g.exit_price, w.exit_price),
            ] {
                assert!((a - b).abs() <= 1e-9, "{tag} {name}: {a} vs {b}");
            }
            assert!(
                (g.pnl_pct - w.pnl_pct).abs() <= 1e-12,
                "{tag} pnl: {} vs {}",
                g.pnl_pct,
                w.pnl_pct
            );
            assert_eq!(
                (g.hit_sl, g.hit_target),
                (w.hit_sl, w.hit_target),
                "{tag} exits"
            );
            total += 1;
        }
    }
    assert!(
        total >= 50,
        "expected a meaningful ext trade corpus, got {total}"
    );
}
