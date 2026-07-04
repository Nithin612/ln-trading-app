//! Candlestick pattern detectors — faithful port of
//! backend/app/analysis/patterns/{single,multi}.py (SIGNAL_ENGINE.md
//! §2.1–2.2). Same thresholds, same scores, same tie behavior; context
//! flags (at_swing_low/high, from the confluence layer) are parameters
//! exactly as in Python.

use crate::types::{Bar, PatternHit};

// ── single-candle (§2.1) ─────────────────────────────────────────────────────

pub fn detect_marubozu(bars: &[Bar]) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("MARUBOZU");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("MARUBOZU");
    }
    let ratio = c.body() / rng;
    if ratio >= 0.95 {
        if c.is_green() {
            return PatternHit::hit(0.8, "MARUBOZU_BULLISH");
        }
        return PatternHit::hit(-0.8, "MARUBOZU_BEARISH");
    }
    PatternHit::miss("MARUBOZU")
}

pub fn detect_doji(bars: &[Bar]) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("DOJI");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("DOJI");
    }
    if c.body() / rng <= 0.05 {
        return PatternHit::hit(0.0, "DOJI");
    }
    PatternHit::miss("DOJI")
}

pub fn detect_spinning_top(bars: &[Bar]) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("SPINNING_TOP");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("SPINNING_TOP");
    }
    let (uw, lw) = (c.upper_wick(), c.lower_wick());
    if c.body() / rng <= 0.30 && uw > 0.0 && lw > 0.0 {
        let sym = uw.min(lw) / uw.max(lw);
        if sym >= 0.5 {
            return PatternHit::hit(0.0, "SPINNING_TOP");
        }
    }
    PatternHit::miss("SPINNING_TOP")
}

/// Hammer shape: body in upper third, lower wick ≥ 2× body, upper ≤ body.
/// With swing-low confirmation → +0.7 HAMMER; else +0.4 PAPER_UMBRELLA.
pub fn detect_hammer(bars: &[Bar], at_swing_low: bool) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("HAMMER");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("HAMMER");
    }
    let body = c.body();
    let (uw, lw) = (c.upper_wick(), c.lower_wick());
    let body_in_upper_third = (c.body_top() - c.low) >= rng * 2.0 / 3.0;
    if body_in_upper_third && body > 0.0 && lw >= 2.0 * body && uw <= body {
        if at_swing_low {
            return PatternHit::hit(0.7, "HAMMER");
        }
        return PatternHit::hit(0.4, "PAPER_UMBRELLA");
    }
    PatternHit::miss("HAMMER")
}

pub fn detect_hanging_man(bars: &[Bar], at_swing_high: bool) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("HANGING_MAN");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("HANGING_MAN");
    }
    let body = c.body();
    let (uw, lw) = (c.upper_wick(), c.lower_wick());
    let body_in_upper_third = (c.body_top() - c.low) >= rng * 2.0 / 3.0;
    if body_in_upper_third && body > 0.0 && lw >= 2.0 * body && uw <= body && at_swing_high {
        return PatternHit::hit(-0.6, "HANGING_MAN");
    }
    PatternHit::miss("HANGING_MAN")
}

pub fn detect_shooting_star(bars: &[Bar], at_swing_high: bool) -> PatternHit {
    let Some(c) = bars.last() else {
        return PatternHit::miss("SHOOTING_STAR");
    };
    let rng = c.range();
    if rng == 0.0 {
        return PatternHit::miss("SHOOTING_STAR");
    }
    let body = c.body();
    let (uw, lw) = (c.upper_wick(), c.lower_wick());
    let body_in_lower_third = (c.high - c.body_bot()) >= rng * 2.0 / 3.0;
    if body_in_lower_third && body > 0.0 && uw >= 2.0 * body && lw <= body && at_swing_high {
        return PatternHit::hit(-0.7, "SHOOTING_STAR");
    }
    PatternHit::miss("SHOOTING_STAR")
}

// ── multi-candle (§2.2) ──────────────────────────────────────────────────────

fn last_two(bars: &[Bar]) -> Option<(&Bar, &Bar)> {
    match bars {
        [.., prev, curr] => Some((prev, curr)),
        _ => None,
    }
}

pub fn detect_engulfing(bars: &[Bar]) -> PatternHit {
    let Some((prev, curr)) = last_two(bars) else {
        return PatternHit::miss("ENGULFING");
    };
    if prev.is_red()
        && curr.is_green()
        && curr.body_bot() <= prev.body_bot()
        && curr.body_top() >= prev.body_top()
    {
        return PatternHit::hit(0.9, "BULLISH_ENGULFING");
    }
    if prev.is_green()
        && curr.is_red()
        && curr.body_top() >= prev.body_top()
        && curr.body_bot() <= prev.body_bot()
    {
        return PatternHit::hit(-0.9, "BEARISH_ENGULFING");
    }
    PatternHit::miss("ENGULFING")
}

pub fn detect_harami(bars: &[Bar]) -> PatternHit {
    let Some((prev, curr)) = last_two(bars) else {
        return PatternHit::miss("HARAMI");
    };
    let inside = curr.body_bot() >= prev.body_bot() && curr.body_top() <= prev.body_top();
    if !inside {
        return PatternHit::miss("HARAMI");
    }
    if prev.is_red() && curr.is_green() {
        return PatternHit::hit(0.5, "BULLISH_HARAMI");
    }
    if prev.is_green() && curr.is_red() {
        return PatternHit::hit(-0.5, "BEARISH_HARAMI");
    }
    PatternHit::miss("HARAMI")
}

pub fn detect_piercing_dark_cloud(bars: &[Bar]) -> PatternHit {
    let Some((prev, curr)) = last_two(bars) else {
        return PatternHit::miss("PIERCING_DCC");
    };
    let prev_mid = (prev.body_bot() + prev.body_top()) / 2.0;

    if prev.is_red()
        && curr.is_green()
        && curr.open < prev.close
        && curr.close > prev_mid
        && curr.close < prev.open
    {
        return PatternHit::hit(0.7, "PIERCING_PATTERN");
    }
    if prev.is_green()
        && curr.is_red()
        && curr.open > prev.close
        && curr.close < prev_mid
        && curr.close > prev.open
    {
        return PatternHit::hit(-0.7, "DARK_CLOUD_COVER");
    }
    PatternHit::miss("PIERCING_DCC")
}

pub fn detect_morning_evening_star(bars: &[Bar]) -> PatternHit {
    let [.., first, star, third] = bars else {
        return PatternHit::miss("STAR");
    };
    let first_mid = (first.body_bot() + first.body_top()) / 2.0;
    let star_small = star.body() < first.body() * 0.5;

    if first.is_red() && third.is_green() && star_small && third.close > first_mid {
        return PatternHit::hit(0.95, "MORNING_STAR");
    }
    if first.is_green() && third.is_red() && star_small && third.close < first_mid {
        return PatternHit::hit(-0.95, "EVENING_STAR");
    }
    PatternHit::miss("STAR")
}
