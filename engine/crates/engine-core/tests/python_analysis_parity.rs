//! Patterns + structure vs the frozen Python analysis code on 49 real
//! market windows. Contract: scores EXACTLY equal (bit-for-bit f64) —
//! these are rule outcomes, not smoothed math.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::collections::HashMap;

use engine_core::patterns as pat;
use engine_core::structure as st;
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
    end: u32,
    bars: Vec<RawBar>,
    expected: HashMap<String, f64>,
}

#[derive(Deserialize)]
struct Fixture {
    cases: Vec<Case>,
}

fn bars_of(case: &Case) -> Vec<Bar> {
    case.bars
        .iter()
        .map(|b| Bar {
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
            volume: b.volume,
        })
        .collect()
}

fn check(case: &Case, key: &str, got: f64) {
    let want = *case
        .expected
        .get(key)
        .unwrap_or_else(|| panic!("{key} missing in fixture"));
    assert!(
        got == want,
        "{}@{} {key}: got {got}, want {want}",
        case.symbol,
        case.end
    );
}

#[test]
fn all_windows_match_python() {
    let raw = include_str!("fixtures/python_analysis_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    assert!(fx.cases.len() >= 40, "fixture too small");

    for case in &fx.cases {
        let bars = bars_of(case);

        check(case, "marubozu", pat::detect_marubozu(&bars).score);
        check(case, "doji", pat::detect_doji(&bars).score);
        check(case, "spinning_top", pat::detect_spinning_top(&bars).score);
        check(case, "engulfing", pat::detect_engulfing(&bars).score);
        check(case, "harami", pat::detect_harami(&bars).score);
        check(
            case,
            "piercing_dcc",
            pat::detect_piercing_dark_cloud(&bars).score,
        );
        check(case, "star", pat::detect_morning_evening_star(&bars).score);

        check(case, "hammer_false", pat::detect_hammer(&bars, false).score);
        check(case, "hammer_true", pat::detect_hammer(&bars, true).score);
        check(
            case,
            "hanging_man_false",
            pat::detect_hanging_man(&bars, false).score,
        );
        check(
            case,
            "hanging_man_true",
            pat::detect_hanging_man(&bars, true).score,
        );
        check(
            case,
            "shooting_star_false",
            pat::detect_shooting_star(&bars, false).score,
        );
        check(
            case,
            "shooting_star_true",
            pat::detect_shooting_star(&bars, true).score,
        );

        check(case, "dow", st::dow_trend_score(&bars, 20, 3));
        check(
            case,
            "sr_none",
            st::sr_zone_score(&bars, None, false, false, false),
        );
        check(
            case,
            "sr_bull",
            st::sr_zone_score(&bars, None, true, false, false),
        );
        check(
            case,
            "sr_bear",
            st::sr_zone_score(&bars, None, false, true, false),
        );
        check(
            case,
            "sr_brk",
            st::sr_zone_score(&bars, None, false, false, true),
        );
        check(case, "fib", st::fibonacci_score(&bars));
    }
}
