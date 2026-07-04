//! Integration parity test: every indicator vs the committed pandas-ta
//! 0.4.71b0 reference fixture. Tolerance tiers per .claude/rules/rust.md:
//! EMA family 1e-9 relative · Wilder family 1e-6 relative.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use engine_core::indicators;
use serde::Deserialize;

#[derive(Deserialize)]
struct Fixture {
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: Vec<f64>,
    ema5: Vec<Option<f64>>,
    rsi14: Vec<Option<f64>>,
    sma20: Vec<Option<f64>>,
    vol_sma20: Vec<Option<f64>>,
    macd_line: Vec<Option<f64>>,
    macd_signal: Vec<Option<f64>>,
    macd_hist: Vec<Option<f64>>,
    atr14: Vec<Option<f64>>,
    adx14: Vec<Option<f64>>,
    dmp14: Vec<Option<f64>>,
    dmn14: Vec<Option<f64>>,
    bb_lower: Vec<Option<f64>>,
    bb_mid: Vec<Option<f64>>,
    bb_upper: Vec<Option<f64>>,
}

fn fixture() -> Fixture {
    let raw = include_str!("fixtures/pandas_ta_reference.json");
    serde_json::from_str(raw).expect("fixture parses")
}

fn assert_series(name: &str, got: &[f64], want: &[Option<f64>], rel_tol: f64) {
    assert_eq!(got.len(), want.len(), "{name}: length mismatch");
    for (i, (g, w)) in got.iter().zip(want.iter()).enumerate() {
        match w {
            None => assert!(g.is_nan(), "{name}[{i}]: expected NaN warmup, got {g}"),
            Some(w) => {
                let denom = w.abs().max(1e-12);
                let rel = (g - w).abs() / denom;
                assert!(
                    rel <= rel_tol,
                    "{name}[{i}]: got {g}, want {w} (rel err {rel:.3e} > {rel_tol:.0e})"
                );
            }
        }
    }
}

#[test]
fn ema_matches() {
    let f = fixture();
    assert_series("ema5", &indicators::ema(&f.close, 5), &f.ema5, 1e-9);
}

#[test]
fn rsi_matches() {
    let f = fixture();
    assert_series("rsi14", &indicators::rsi(&f.close, 14), &f.rsi14, 1e-6);
}

#[test]
fn sma_matches() {
    let f = fixture();
    assert_series("sma20", &indicators::sma(&f.close, 20), &f.sma20, 1e-9);
    assert_series(
        "vol_sma20",
        &indicators::sma(&f.volume, 20),
        &f.vol_sma20,
        1e-9,
    );
}

#[test]
fn macd_matches() {
    let f = fixture();
    let (line, signal, hist) = indicators::macd(&f.close, 12, 26, 9);
    assert_series("macd_line", &line, &f.macd_line, 1e-9);
    assert_series("macd_signal", &signal, &f.macd_signal, 1e-9);
    // histogram is a small difference of larger numbers — absolute-ish tier
    // via relative-to-line scale is too strict; hold it to 1e-6 relative.
    assert_series("macd_hist", &hist, &f.macd_hist, 1e-6);
}

#[test]
fn atr_matches() {
    let f = fixture();
    assert_series(
        "atr14",
        &indicators::atr(&f.high, &f.low, &f.close, 14),
        &f.atr14,
        1e-6,
    );
}

#[test]
fn adx_matches() {
    let f = fixture();
    let (adx, dmp, dmn) = indicators::adx(&f.high, &f.low, &f.close, 14);
    assert_series("adx14", &adx, &f.adx14, 1e-6);
    assert_series("dmp14", &dmp, &f.dmp14, 1e-6);
    assert_series("dmn14", &dmn, &f.dmn14, 1e-6);
}

#[test]
fn bbands_matches() {
    let f = fixture();
    let (lo, mid, up) = indicators::bbands(&f.close, 20, 2.0);
    assert_series("bb_lower", &lo, &f.bb_lower, 1e-9);
    assert_series("bb_mid", &mid, &f.bb_mid, 1e-9);
    assert_series("bb_upper", &up, &f.bb_upper, 1e-9);
}
