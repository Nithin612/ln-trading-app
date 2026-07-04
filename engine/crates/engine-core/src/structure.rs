//! Structural factors — faithful port of backend/app/analysis/structure/
//! {dow,levels,fibonacci}.py (SIGNAL_ENGINE.md §2.4–2.6). Scores exact;
//! explanation strings stay Python-side.

use crate::pivots::{swing_high_indices, swing_low_indices};
use crate::types::Bar;

pub const PROXIMITY_PCT: f64 = 0.005;
const MIN_STRENGTH: usize = 2;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ZoneType {
    Support,
    Resistance,
    DemandZone,
    SupplyZone,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Zone {
    pub price_lower: f64,
    pub price_upper: f64,
    pub zone_type: ZoneType,
    pub strength: usize,
}

// ── Dow trend (§2.4) ─────────────────────────────────────────────────────────

/// Score for the DOW_TREND factor. Python parity: lookback window of 20,
/// pivots with wing `swing_n` on that window, last two swing highs/lows,
/// recent-3-bar break check → ±0.35 flip signal, else ±0.7 / 0.0.
pub fn dow_trend_score(bars: &[Bar], lookback: usize, swing_n: usize) -> f64 {
    if bars.len() < lookback + swing_n * 2 + 1 {
        return 0.0;
    }
    let start = bars.len().saturating_sub(lookback);
    let window = bars.get(start..).unwrap_or(&[]);
    let highs: Vec<f64> = window.iter().map(|b| b.high).collect();
    let lows: Vec<f64> = window.iter().map(|b| b.low).collect();

    let hi_idx = swing_high_indices(&highs, swing_n);
    let lo_idx = swing_low_indices(&lows, swing_n);
    if hi_idx.len() < 2 || lo_idx.len() < 2 {
        return 0.0;
    }

    let get = |v: &[f64], i: usize| v.get(i).copied().unwrap_or(f64::NAN);
    let last_two = |v: &[usize]| match v {
        [.., a, b] => (*a, *b),
        _ => (0, 0),
    };
    let (sh1, sh2) = last_two(&hi_idx);
    let (sl1, sl2) = last_two(&lo_idx);

    let hh = get(&highs, sh2) > get(&highs, sh1);
    let hl = get(&lows, sl2) > get(&lows, sl1);
    let lh = get(&highs, sh2) < get(&highs, sh1);
    let ll = get(&lows, sl2) < get(&lows, sl1);

    // last-3 bars of the FULL series (Python uses candles, not the window)
    let tail_start = bars.len().saturating_sub(3);
    let tail = bars.get(tail_start..).unwrap_or(&[]);
    let last3_hi = tail
        .iter()
        .map(|b| b.high)
        .fold(f64::NEG_INFINITY, f64::max);
    let last3_lo = tail.iter().map(|b| b.low).fold(f64::INFINITY, f64::min);

    if hh && hl {
        if last3_lo < get(&lows, sl2) {
            return -0.35;
        }
        return 0.7;
    }
    if lh && ll {
        if last3_hi > get(&highs, sh2) {
            return 0.35;
        }
        return -0.7;
    }
    0.0
}

// ── S/R levels + demand/supply zones (§2.5) ─────────────────────────────────

/// Swing-pivot S/R zones tested ≥2 times. Python parity: greedy clustering
/// over SORTED pivot prices, proximity measured against the FIRST element
/// of the current cluster.
pub fn detect_sr_levels(bars: &[Bar], n: usize) -> Vec<Zone> {
    let highs: Vec<f64> = bars.iter().map(|b| b.high).collect();
    let lows: Vec<f64> = bars.iter().map(|b| b.low).collect();

    let resistance: Vec<f64> = swing_high_indices(&highs, n)
        .into_iter()
        .filter_map(|i| highs.get(i).copied())
        .collect();
    let support: Vec<f64> = swing_low_indices(&lows, n)
        .into_iter()
        .filter_map(|i| lows.get(i).copied())
        .collect();

    let mut zones = cluster(&resistance, ZoneType::Resistance);
    zones.extend(cluster(&support, ZoneType::Support));
    zones
}

fn cluster(prices: &[f64], zone_type: ZoneType) -> Vec<Zone> {
    let mut sorted: Vec<f64> = prices.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let mut zones = Vec::new();
    let Some(&first) = sorted.first() else {
        return zones;
    };
    let mut cluster: Vec<f64> = vec![first];

    let flush = |cluster: &[f64], zones: &mut Vec<Zone>| {
        if cluster.len() >= MIN_STRENGTH {
            let mid = cluster.iter().sum::<f64>() / cluster.len() as f64;
            zones.push(Zone {
                price_lower: mid * (1.0 - PROXIMITY_PCT),
                price_upper: mid * (1.0 + PROXIMITY_PCT),
                zone_type,
                strength: cluster.len(),
            });
        }
    };

    for &p in sorted.get(1..).unwrap_or(&[]) {
        let anchor = cluster.first().copied().unwrap_or(p);
        if (p - anchor) / anchor <= PROXIMITY_PCT {
            cluster.push(p);
        } else {
            flush(&cluster, &mut zones);
            cluster = vec![p];
        }
    }
    flush(&cluster, &mut zones);
    zones
}

/// Demand/supply zones: last opposite-color candle before a "big" move
/// (body > 1.5× the mean body over the WHOLE window).
pub fn detect_demand_supply_zones(bars: &[Bar]) -> Vec<Zone> {
    if bars.is_empty() {
        return Vec::new();
    }
    let avg_body = bars.iter().map(Bar::body).sum::<f64>() / bars.len() as f64;
    let mut zones = Vec::new();
    for pair in bars.windows(2) {
        let [prev, curr] = pair else { continue };
        let is_big = curr.body() > 1.5 * avg_body;
        // Python: curr_green uses close > open (STRICT — differs from is_green)
        let curr_green = curr.close > curr.open;
        let curr_red = curr.close < curr.open;
        let prev_green = prev.close > prev.open;
        let prev_red = prev.close < prev.open;
        if is_big && curr_green && prev_red {
            zones.push(Zone {
                price_lower: prev.low,
                price_upper: prev.high,
                zone_type: ZoneType::DemandZone,
                strength: 1,
            });
        }
        if is_big && curr_red && prev_green {
            zones.push(Zone {
                price_lower: prev.low,
                price_upper: prev.high,
                zone_type: ZoneType::SupplyZone,
                strength: 1,
            });
        }
    }
    zones
}

/// SR_ZONE factor score. Python parity: iterate sr_levels(n=3) then
/// demand/supply zones IN ORDER, keep the highest |score| (strict >, so
/// first-seen wins ties).
pub fn sr_zone_score(
    bars: &[Bar],
    current_price: Option<f64>,
    bullish_pattern: bool,
    bearish_pattern: bool,
    breakout_volume_ok: bool,
) -> f64 {
    let Some(last) = bars.last() else {
        return 0.0;
    };
    let price = current_price.unwrap_or(last.close);

    let mut all = detect_sr_levels(bars, 3);
    all.extend(detect_demand_supply_zones(bars));

    let mut best = 0.0_f64;
    for z in &all {
        let prox_lower = (price - z.price_lower).abs() / price;
        let prox_upper = (price - z.price_upper).abs() / price;
        let at_level = prox_lower <= PROXIMITY_PCT
            || prox_upper <= PROXIMITY_PCT
            || (z.price_lower <= price && price <= z.price_upper);
        if !at_level {
            continue;
        }
        let s: f64 = match z.zone_type {
            ZoneType::Support if bullish_pattern => 0.8,
            ZoneType::Resistance if bearish_pattern => -0.8,
            ZoneType::DemandZone if bullish_pattern => 0.85,
            ZoneType::SupplyZone if bearish_pattern => -0.85,
            ZoneType::Resistance if breakout_volume_ok => 0.9,
            ZoneType::Support if breakout_volume_ok => -0.9,
            _ => continue,
        };
        if s.abs() > best.abs() {
            best = s;
        }
    }
    best
}

// ── Fibonacci (§2.6) ─────────────────────────────────────────────────────────

/// FIBONACCI factor score. Python parity: swing = max(high)/min(low) over
/// all bars EXCEPT the last; levels 0.5→+0.4, 0.618→+0.6, 0.786→+0.4 within
/// 0.5% proximity (highest |score| wins, iteration order 0.5, 0.618, 0.786);
/// close < swing_low → −0.5 (checked AFTER level proximity, overriding it).
pub fn fibonacci_score(bars: &[Bar]) -> f64 {
    if bars.len() < 20 {
        return 0.0;
    }
    let prior = bars.get(..bars.len() - 1).unwrap_or(&[]);
    let swing_high = prior
        .iter()
        .map(|b| b.high)
        .fold(f64::NEG_INFINITY, f64::max);
    let swing_low = prior.iter().map(|b| b.low).fold(f64::INFINITY, f64::min);
    let swing_range = swing_high - swing_low;
    if swing_range <= 0.0 {
        return 0.0;
    }
    let close = bars.last().map(|b| b.close).unwrap_or(f64::NAN);

    let mut best = 0.0_f64;
    let levels: [(f64, f64); 3] = [(0.500, 0.4), (0.618, 0.6), (0.786, 0.4)];
    for (ratio, score) in levels {
        let fib_price = swing_high - ratio * swing_range;
        if fib_price <= 0.0 {
            continue;
        }
        if (close - fib_price).abs() / fib_price <= PROXIMITY_PCT && score.abs() > best.abs() {
            best = score;
        }
    }
    if close < swing_low {
        return -0.5;
    }
    best
}
