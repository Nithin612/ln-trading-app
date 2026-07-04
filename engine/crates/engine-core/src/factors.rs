//! Factor functions — faithful port of backend/app/analysis/indicators/*
//! factor layers and structure/institutional.py (SIGNAL_ENGINE.md §2.3,
//! §2.7). Numeric inputs come from indicators.rs (machine-identical to
//! pandas-ta); rule thresholds and scores replicate Python exactly.

use crate::indicators;
use crate::types::Bar;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Factor {
    pub name: &'static str,
    pub weight: f64,
    pub score: f64,
    pub is_pattern: bool,
    pub is_indicator: bool,
}

impl Factor {
    pub const fn new(name: &'static str, weight: f64, score: f64) -> Self {
        Self {
            name,
            weight,
            score,
            is_pattern: false,
            is_indicator: false,
        }
    }
    pub const fn indicator(name: &'static str, weight: f64, score: f64) -> Self {
        Self {
            name,
            weight,
            score,
            is_pattern: false,
            is_indicator: true,
        }
    }
}

fn closes(bars: &[Bar]) -> Vec<f64> {
    bars.iter().map(|b| b.close).collect()
}

fn last2(v: &[f64]) -> Option<(f64, f64)> {
    match v {
        [.., a, b] if !a.is_nan() && !b.is_nan() => Some((*a, *b)),
        _ => None,
    }
}

// ── EMA family (§2.3) ────────────────────────────────────────────────────────

pub fn ema_cross_factor(bars: &[Bar]) -> Factor {
    let c = closes(bars);
    let e20 = indicators::ema(&c, 20);
    let e50 = indicators::ema(&c, 50);
    // Python: any-valid check + needs index -2; NaN at -2 (fresh seed) makes
    // the comparisons False → 0.0, which last2's NaN guard reproduces.
    let (Some((e20_prev, e20_now)), Some((e50_prev, e50_now))) = (last2(&e20), last2(&e50)) else {
        let any_valid =
            e20.last().is_some_and(|v| !v.is_nan()) && e50.last().is_some_and(|v| !v.is_nan());
        let _ = any_valid; // both paths score 0.0, matching Python
        return Factor::new("EMA_CROSS", 15.0, 0.0);
    };
    if e20_prev <= e50_prev && e20_now > e50_now {
        return Factor {
            is_indicator: true,
            ..Factor::new("EMA_CROSS", 15.0, 0.6)
        };
    }
    if e20_prev >= e50_prev && e20_now < e50_now {
        return Factor {
            is_indicator: true,
            ..Factor::new("EMA_CROSS", 15.0, -0.6)
        };
    }
    Factor::new("EMA_CROSS", 15.0, 0.0)
}

pub fn price_vs_ema_factor(bars: &[Bar]) -> Factor {
    let c = closes(bars);
    let close_now = c.last().copied().unwrap_or(f64::NAN);
    let e50 = indicators::ema(&c, 50).last().copied().unwrap_or(f64::NAN);
    let e200 = indicators::ema(&c, 200).last().copied().unwrap_or(f64::NAN);
    if e50.is_nan() || e200.is_nan() {
        return Factor::new("PRICE_VS_EMA", 15.0, 0.0);
    }
    if close_now > e50 && e50 > e200 {
        return Factor::indicator("PRICE_VS_EMA", 15.0, 0.5);
    }
    if close_now < e50 && e50 < e200 {
        return Factor::indicator("PRICE_VS_EMA", 15.0, -0.5);
    }
    Factor::new("PRICE_VS_EMA", 15.0, 0.0)
}

/// Multibagger bonus (1d only): 20 EMA within 2% of 200 EMA + green
/// breakout candle with body ≥ 1.5× the mean |body| of the last 20 bars.
pub fn multibagger_ema_factor(bars: &[Bar]) -> Factor {
    let c = closes(bars);
    let e20 = indicators::ema(&c, 20).last().copied().unwrap_or(f64::NAN);
    let e200 = indicators::ema(&c, 200).last().copied().unwrap_or(f64::NAN);
    if e20.is_nan() || e200.is_nan() || e200 == 0.0 {
        return Factor::new("MULTIBAGGER_EMA", 10.0, 0.0);
    }
    let proximity_pct = (e20 - e200).abs() / e200 * 100.0;
    if proximity_pct > 2.0 {
        return Factor::new("MULTIBAGGER_EMA", 10.0, 0.0);
    }
    let Some(last) = bars.last() else {
        return Factor::new("MULTIBAGGER_EMA", 10.0, 0.0);
    };
    let tail_start = bars.len().saturating_sub(20);
    let tail = bars.get(tail_start..).unwrap_or(&[]);
    if tail.is_empty() {
        return Factor::new("MULTIBAGGER_EMA", 10.0, 0.0);
    }
    let avg_body = tail.iter().map(Bar::body).sum::<f64>() / tail.len() as f64;
    let breakout = last.close > last.open && last.body() >= 1.5 * avg_body;
    if breakout {
        return Factor::indicator("MULTIBAGGER_EMA", 10.0, 0.9);
    }
    Factor::new("MULTIBAGGER_EMA", 10.0, 0.0)
}

// ── RSI (§2.3) ───────────────────────────────────────────────────────────────

pub fn rsi_level_factor(bars: &[Bar]) -> Factor {
    let rsi = indicators::rsi(&closes(bars), 14);
    let Some((prev, last)) = last2(&rsi) else {
        return Factor::new("RSI_LEVEL", 10.0, 0.0);
    };
    let score = if (30.0..=50.0).contains(&last) && last > prev {
        0.6
    } else if last > 50.0 && last <= 70.0 && last < prev {
        -0.6
    } else if last < 30.0 {
        0.4
    } else if last > 70.0 {
        -0.4
    } else {
        0.0
    };
    if score == 0.0 {
        Factor::new("RSI_LEVEL", 10.0, 0.0)
    } else {
        Factor::indicator("RSI_LEVEL", 10.0, score)
    }
}

pub fn rsi_divergence_factor(bars: &[Bar], lookback: usize) -> Factor {
    if bars.len() < lookback + 1 {
        return Factor::new("RSI_DIVERGENCE", 10.0, 0.0);
    }
    let c = closes(bars);
    let rsi = indicators::rsi(&c, 14);
    let valid = rsi.iter().filter(|v| !v.is_nan()).count();
    if valid < lookback + 1 {
        return Factor::new("RSI_DIVERGENCE", 10.0, 0.0);
    }
    let w_start = bars.len().saturating_sub(lookback + 1);
    let cw = c.get(w_start..).unwrap_or(&[]);
    let rw = rsi.get(w_start..).unwrap_or(&[]);
    let (Some(&price_now), Some(&rsi_now)) = (cw.last(), rw.last()) else {
        return Factor::new("RSI_DIVERGENCE", 10.0, 0.0);
    };
    let prior_c = cw.get(..cw.len() - 1).unwrap_or(&[]);
    let prior_r = rw.get(..rw.len() - 1).unwrap_or(&[]);
    let price_low_prev = prior_c.iter().copied().fold(f64::INFINITY, f64::min);
    let price_high_prev = prior_c.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let rsi_low_prev = prior_r.iter().copied().fold(f64::INFINITY, f64::min);
    let rsi_high_prev = prior_r.iter().copied().fold(f64::NEG_INFINITY, f64::max);

    if price_now < price_low_prev && rsi_now > rsi_low_prev {
        return Factor::indicator("RSI_DIVERGENCE", 10.0, 0.8);
    }
    if price_now > price_high_prev && rsi_now < rsi_high_prev {
        return Factor::indicator("RSI_DIVERGENCE", 10.0, -0.8);
    }
    Factor::new("RSI_DIVERGENCE", 10.0, 0.0)
}

// ── MACD (§2.3) ──────────────────────────────────────────────────────────────

pub fn macd_cross_factor(bars: &[Bar]) -> Factor {
    let (line, signal, _hist) = indicators::macd(&closes(bars), 12, 26, 9);
    let (Some((m_prev, m_now)), Some((s_prev, s_now))) = (last2(&line), last2(&signal)) else {
        return Factor::new("MACD_CROSS", 10.0, 0.0);
    };
    if m_prev < s_prev && m_now >= s_now {
        return Factor::indicator("MACD_CROSS", 10.0, 0.7);
    }
    if m_prev > s_prev && m_now <= s_now {
        return Factor::indicator("MACD_CROSS", 10.0, -0.7);
    }
    Factor::new("MACD_CROSS", 10.0, 0.0)
}

pub fn macd_histogram_factor(bars: &[Bar]) -> Factor {
    let (_line, _signal, hist) = indicators::macd(&closes(bars), 12, 26, 9);
    let Some((h_prev, h_now)) = last2(&hist) else {
        return Factor::new("MACD_HISTOGRAM", 10.0, 0.0);
    };
    if h_now < 0.0 && h_now > h_prev {
        return Factor::indicator("MACD_HISTOGRAM", 10.0, 0.4);
    }
    if h_now > 0.0 && h_now < h_prev {
        return Factor::indicator("MACD_HISTOGRAM", 10.0, -0.4);
    }
    Factor::new("MACD_HISTOGRAM", 10.0, 0.0)
}

// ── Volume (§2.3) ────────────────────────────────────────────────────────────

/// AS-IS port: +0.5 on any ≥1.5× surge regardless of direction (the
/// direction-match question is adjudication item A — applied to both
/// engines together once decided).
pub fn volume_factor(bars: &[Bar]) -> Factor {
    const AVG_PERIOD: usize = 20;
    if bars.len() < AVG_PERIOD + 1 {
        return Factor::new("VOLUME", 10.0, 0.0);
    }
    let start = bars.len() - AVG_PERIOD - 1;
    let window = bars.get(start..bars.len() - 1).unwrap_or(&[]);
    let avg = window.iter().map(|b| b.volume).sum::<f64>() / AVG_PERIOD as f64;
    let curr = bars.last().map(|b| b.volume).unwrap_or(0.0);
    if avg == 0.0 {
        return Factor::new("VOLUME", 10.0, 0.0);
    }
    if curr / avg >= 1.5 {
        return Factor::indicator("VOLUME", 10.0, 0.5);
    }
    Factor::new("VOLUME", 10.0, 0.0)
}

// ── Bollinger reversal (§2.3) ────────────────────────────────────────────────

pub fn bbands_factor(bars: &[Bar]) -> Factor {
    let c = closes(bars);
    let (lower, _mid, upper) = indicators::bbands(&c, 20, 2.0);
    let (Some((lo_prev, lo_now)), Some((up_prev, up_now)), Some((c_prev, c_now))) =
        (last2(&lower), last2(&upper), last2(&c))
    else {
        return Factor::new("BBANDS", 10.0, 0.0);
    };
    if c_prev <= lo_prev && c_now > lo_now {
        return Factor::indicator("BBANDS", 10.0, 0.5);
    }
    if c_prev >= up_prev && c_now < up_now {
        return Factor::indicator("BBANDS", 10.0, -0.5);
    }
    Factor::new("BBANDS", 10.0, 0.0)
}

// ── ADX (§2.3) ───────────────────────────────────────────────────────────────

fn last_adx(bars: &[Bar]) -> Option<(f64, f64, f64)> {
    let highs: Vec<f64> = bars.iter().map(|b| b.high).collect();
    let lows: Vec<f64> = bars.iter().map(|b| b.low).collect();
    let closes_v: Vec<f64> = bars.iter().map(|b| b.close).collect();
    let (adx, dmp, dmn) = indicators::adx(&highs, &lows, &closes_v, 14);
    match (adx.last(), dmp.last(), dmn.last()) {
        (Some(a), Some(p), Some(m)) if !a.is_nan() => Some((*a, *p, *m)),
        _ => None,
    }
}

pub fn adx_factor(bars: &[Bar]) -> Factor {
    let Some((adx, dmp, dmn)) = last_adx(bars) else {
        return Factor::new("ADX", 5.0, 0.0);
    };
    if adx > 25.0 {
        if dmp > dmn {
            return Factor::indicator("ADX", 5.0, 0.6);
        }
        return Factor::indicator("ADX", 5.0, -0.6);
    }
    Factor::new("ADX", 5.0, 0.0)
}

pub fn adx_is_strong(bars: &[Bar]) -> bool {
    last_adx(bars).is_some_and(|(a, _, _)| a > 40.0)
}

pub fn adx_is_weak(bars: &[Bar]) -> bool {
    last_adx(bars).is_some_and(|(a, _, _)| a < 20.0)
}

// ── FII/DII institutional flow (§2.7) ───────────────────────────────────────

pub fn fii_dii_factor(fii_net_5d: f64, dii_net_5d: f64, block_deal_net_cr: f64) -> Factor {
    const FII_T: f64 = 2000.0;
    const DII_T: f64 = 1500.0;
    let mut score: f64 = 0.0;
    if fii_net_5d > FII_T {
        score += 0.5;
    } else if fii_net_5d < -FII_T {
        score -= 0.5;
    }
    if fii_net_5d < 0.0 && dii_net_5d > DII_T {
        score += 0.3;
    }
    if fii_net_5d > FII_T && dii_net_5d > DII_T {
        score = 0.7;
    }
    if block_deal_net_cr > 0.0 {
        score = (score + 0.4).min(1.0);
    } else if block_deal_net_cr < 0.0 {
        score = (score - 0.4).max(-1.0);
    }
    score = score.clamp(-1.0, 1.0);
    Factor {
        name: "FII_DII_FLOW",
        weight: 5.0,
        score,
        is_pattern: false,
        is_indicator: false,
    }
}
