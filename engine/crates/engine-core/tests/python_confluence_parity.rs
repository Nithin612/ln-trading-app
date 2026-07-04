//! Full-pipeline parity: run_all_factors + score_from_factors vs the frozen
//! Python engine on 84 real 320-bar windows (EMA-200 active). Contract:
//! factor scores bit-for-bit; confidence integers exact; signal decisions
//! (fire/no-fire + direction) exact; normalized within 1e-12.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::collections::HashMap;

use engine_core::confluence::{run_all_factors, score_from_factors, Direction, FlowInputs};
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
struct FactorExp {
    w: f64,
    s: f64,
}

#[derive(Deserialize)]
struct OutcomeExp {
    direction: String,
    confidence: i32,
    normalized: f64,
    multibagger: bool,
}

#[derive(Deserialize)]
struct Case {
    symbol: String,
    end: u32,
    bars: Vec<RawBar>,
    factors: HashMap<String, FactorExp>,
    outcome: Option<OutcomeExp>,
}

#[derive(Deserialize)]
struct Fixture {
    cases: Vec<Case>,
}

#[test]
fn full_pipeline_matches_python() {
    let raw = include_str!("fixtures/python_confluence_reference.json");
    let fx: Fixture = serde_json::from_str(raw).expect("fixture parses");
    assert!(fx.cases.len() >= 60, "fixture too small");
    let mut fired = 0;

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

        let raw = run_all_factors(&bars, "1d", FlowInputs::default());
        // The fixture records POST-adjustment scores (item A lives in the
        // scorer); apply the same volume adjustment before comparing.
        let rest: f64 = raw
            .iter()
            .filter(|f| f.name != "VOLUME")
            .map(|f| f.weight * f.score)
            .sum();
        let factors: Vec<_> = raw
            .iter()
            .map(|f| {
                if f.name == "VOLUME" && f.score > 0.0 {
                    let s = if rest > 0.0 {
                        0.5
                    } else if rest < 0.0 {
                        -0.5
                    } else {
                        0.0
                    };
                    engine_core::factors::Factor { score: s, ..*f }
                } else {
                    *f
                }
            })
            .collect();

        // Every Python factor present with the same weight and EXACT score.
        // (PATTERN factor's name varies with the winning detector.)
        assert_eq!(
            factors.len(),
            case.factors.len(),
            "{}@{}: factor count",
            case.symbol,
            case.end
        );
        for f in &factors {
            let exp = case.factors.get(f.name).unwrap_or_else(|| {
                panic!("{}@{}: unexpected factor {}", case.symbol, case.end, f.name)
            });
            assert!(
                exp.w == f.weight && exp.s == f.score,
                "{}@{} {}: got (w={}, s={}), want (w={}, s={})",
                case.symbol,
                case.end,
                f.name,
                f.weight,
                f.score,
                exp.w,
                exp.s
            );
        }

        let outcome = score_from_factors(&raw, &bars, 70);
        match (&outcome, &case.outcome) {
            (None, None) => {}
            (Some(got), Some(want)) => {
                fired += 1;
                let dir = match got.direction {
                    Direction::Buy => "BUY",
                    Direction::Sell => "SELL",
                };
                assert_eq!(dir, want.direction, "{}@{}", case.symbol, case.end);
                assert_eq!(
                    got.confidence_pct, want.confidence,
                    "{}@{}",
                    case.symbol, case.end
                );
                assert!(
                    (got.normalized - want.normalized).abs() <= 1e-12,
                    "{}@{} normalized {} vs {}",
                    case.symbol,
                    case.end,
                    got.normalized,
                    want.normalized
                );
                assert_eq!(got.is_multibagger, want.multibagger);
            }
            (got, want) => panic!(
                "{}@{}: decision mismatch — rust fired={}, python fired={}",
                case.symbol,
                case.end,
                got.is_some(),
                want.is_some()
            ),
        }
    }
    assert!(fired >= 1, "expected at least one fired signal in fixture");
}
