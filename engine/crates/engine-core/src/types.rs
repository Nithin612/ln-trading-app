//! Shared data types. Explanation strings stay Python-side; the parity
//! contract for detectors/factors is (detected, score, code) — scores are
//! compared EXACTLY against the frozen Python engine.

/// One OHLCV bar. Indicator/pattern math is f64 by convention
/// (.claude/rules/rust.md); money stays i64·1e-4 elsewhere.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Bar {
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

impl Bar {
    #[inline]
    pub fn body(&self) -> f64 {
        (self.close - self.open).abs()
    }
    #[inline]
    pub fn range(&self) -> f64 {
        self.high - self.low
    }
    #[inline]
    pub fn upper_wick(&self) -> f64 {
        self.high - self.open.max(self.close)
    }
    #[inline]
    pub fn lower_wick(&self) -> f64 {
        self.open.min(self.close) - self.low
    }
    #[inline]
    pub fn body_top(&self) -> f64 {
        self.open.max(self.close)
    }
    #[inline]
    pub fn body_bot(&self) -> f64 {
        self.open.min(self.close)
    }
    /// Python parity: `close >= open` is green (doji counts as green).
    #[inline]
    pub fn is_green(&self) -> bool {
        self.close >= self.open
    }
    #[inline]
    pub fn is_red(&self) -> bool {
        self.close < self.open
    }
}

/// Pattern detector output (mirrors Python PatternResult minus the string).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PatternHit {
    pub detected: bool,
    pub score: f64,
    /// Stable code, e.g. "BULLISH_ENGULFING" — matches the Python `name`.
    pub code: &'static str,
}

impl PatternHit {
    pub const fn miss(code: &'static str) -> Self {
        Self {
            detected: false,
            score: 0.0,
            code,
        }
    }
    pub const fn hit(score: f64, code: &'static str) -> Self {
        Self {
            detected: true,
            score,
            code,
        }
    }
}
