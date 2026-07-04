//! Confluence scorer — faithful port of backend/app/analysis/confluence.py
//! (SIGNAL_ENGINE.md §3). Replication contract (.claude/rules/rust.md):
//! zero-score exclusion from the weight denominator, `int()` TRUNCATION of
//! confidence, multibagger appended only when positive (1d), ADX regime
//! adjustment of the gate, pattern ties resolved first-max like Python.

use crate::factors::{self, Factor};
use crate::patterns as pat;
use crate::structure;
use crate::types::Bar;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    Buy,
    Sell,
}

#[derive(Debug, Clone)]
pub struct ConfluenceOutcome {
    pub direction: Direction,
    pub confidence_pct: i32,
    pub normalized: f64,
    pub factors: Vec<Factor>,
    pub is_multibagger: bool,
}

/// Best single pattern (§2 weights table: one pattern, weight 15, not
/// summed). Context: swing proximity = close within 1% of the 20-bar
/// high/low (NOT pivot-based — Python parity).
fn best_pattern_factor(bars: &[Bar]) -> Factor {
    let Some(last) = bars.last() else {
        return Factor::grouped("PATTERN", 15.0, 0.0, "pattern");
    };
    let close = last.close;
    let start = bars.len().saturating_sub(20);
    let window = bars.get(start..).unwrap_or(bars);
    let high20 = window
        .iter()
        .map(|b| b.high)
        .fold(f64::NEG_INFINITY, f64::max);
    let low20 = window.iter().map(|b| b.low).fold(f64::INFINITY, f64::min);
    let at_swing_low = low20 > 0.0 && (close - low20).abs() / low20 <= 0.01;
    let at_swing_high = high20 > 0.0 && (close - high20).abs() / high20 <= 0.01;

    let candidates = [
        pat::detect_marubozu(bars),
        pat::detect_hammer(bars, at_swing_low),
        pat::detect_hanging_man(bars, at_swing_high),
        pat::detect_shooting_star(bars, at_swing_high),
        pat::detect_engulfing(bars),
        pat::detect_harami(bars),
        pat::detect_piercing_dark_cloud(bars),
        pat::detect_morning_evening_star(bars),
    ];
    // Python max(): first-encountered max wins ties (strict > when scanning).
    let mut best = candidates
        .first()
        .copied()
        .unwrap_or(crate::types::PatternHit::miss("PATTERN"));
    for c in candidates.iter().skip(1) {
        if c.score.abs() > best.score.abs() {
            best = *c;
        }
    }
    Factor {
        name: best.code,
        weight: 15.0,
        score: if best.detected { best.score } else { 0.0 },
        is_pattern: true,
        is_indicator: false,
        group: "pattern",
    }
}

/// Institutional inputs (crore INR) — zeros in backtests today.
#[derive(Debug, Clone, Copy, Default)]
pub struct FlowInputs {
    pub fii_net_5d: f64,
    pub dii_net_5d: f64,
    pub stock_block_deal_net_cr: f64,
}

pub fn run_all_factors(bars: &[Bar], timeframe: &str, flows: FlowInputs) -> Vec<Factor> {
    let swing_n = if matches!(timeframe, "1m" | "5m" | "15m") {
        3
    } else {
        5
    };
    let close = bars.last().map(|b| b.close).unwrap_or(f64::NAN);

    let pattern = best_pattern_factor(bars);
    let bullish_pattern = pattern.score > 0.0;
    let bearish_pattern = pattern.score < 0.0;

    let vol = factors::volume_factor(bars);
    let breakout_volume = vol.score > 0.0;

    let mut out = vec![
        pattern,
        Factor {
            name: "DOW_TREND",
            weight: 20.0,
            score: structure::dow_trend_score(bars, 20, swing_n),
            is_pattern: false,
            is_indicator: false,
            group: "structure",
        },
        factors::ema_cross_factor(bars),
        factors::price_vs_ema_factor(bars),
        factors::rsi_level_factor(bars),
        factors::rsi_divergence_factor(bars, 10),
        factors::macd_cross_factor(bars),
        factors::macd_histogram_factor(bars),
        vol,
        factors::bbands_factor(bars),
        factors::adx_factor(bars),
        Factor {
            name: "SR_ZONE",
            weight: 10.0,
            score: structure::sr_zone_score(
                bars,
                Some(close),
                bullish_pattern,
                bearish_pattern,
                breakout_volume,
            ),
            is_pattern: false,
            is_indicator: false,
            group: "structure",
        },
        Factor {
            name: "FIBONACCI",
            weight: 5.0,
            score: structure::fibonacci_score(bars),
            is_pattern: false,
            is_indicator: false,
            group: "structure",
        },
        factors::fii_dii_factor(
            flows.fii_net_5d,
            flows.dii_net_5d,
            flows.stock_block_deal_net_cr,
        ),
    ];

    if timeframe == "1d" {
        let mb = factors::multibagger_ema_factor(bars);
        if mb.score > 0.0 {
            out.push(mb);
        }
    }
    out
}

/// §3 scorer over a pre-built factor list (weights may be overridden by
/// the strategy lab before this call).
pub fn score_from_factors(
    factors: &[Factor],
    bars: &[Bar],
    min_confidence: i32,
) -> Option<ConfluenceOutcome> {
    // Adjudicated 2026-07-04 (item A): volume "only counts if direction
    // matches" — a surge confirms the OTHER factors, never opposes them,
    // never fires alone. Mirrors Python exactly.
    let rest: f64 = factors
        .iter()
        .filter(|f| f.name != "VOLUME")
        .map(|f| f.weight * f.score)
        .sum();
    let factors: Vec<Factor> = factors
        .iter()
        .map(|f| {
            if f.name == "VOLUME" && f.score > 0.0 {
                let new_score = if rest > 0.0 {
                    0.5
                } else if rest < 0.0 {
                    -0.5
                } else {
                    0.0
                };
                Factor {
                    score: new_score,
                    ..*f
                }
            } else {
                *f
            }
        })
        .collect();
    let factors = factors.as_slice();

    let total_weighted: f64 = factors.iter().map(|f| f.weight * f.score).sum();
    let total_weight: f64 = factors
        .iter()
        .filter(|f| f.score != 0.0)
        .map(|f| f.weight)
        .sum();
    if total_weight == 0.0 {
        return None;
    }
    let normalized = total_weighted / total_weight;
    #[allow(clippy::cast_possible_truncation)]
    let confidence_pct = (normalized.abs() * 100.0).trunc() as i32; // Python int()

    let mut effective_min = min_confidence;
    if factors::adx_is_weak(bars) {
        effective_min += 5;
    } else if factors::adx_is_strong(bars) {
        // Python: max(65, min_confidence - 5)
        effective_min = (min_confidence - 5).max(65);
    }
    if confidence_pct < effective_min {
        return None;
    }

    let direction = if normalized > 0.0 {
        Direction::Buy
    } else {
        Direction::Sell
    };
    let is_multibagger = factors
        .iter()
        .any(|f| f.name == "MULTIBAGGER_EMA" && f.score > 0.0);

    Some(ConfluenceOutcome {
        direction,
        confidence_pct,
        normalized,
        factors: factors.to_vec(),
        is_multibagger,
    })
}

pub fn score_signal(
    bars: &[Bar],
    timeframe: &str,
    min_confidence: i32,
    flows: FlowInputs,
) -> Option<ConfluenceOutcome> {
    let factors = run_all_factors(bars, timeframe, flows);
    score_from_factors(&factors, bars, min_confidence)
}
