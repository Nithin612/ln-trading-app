//! MACD(fast, slow, signal), pandas-ta semantics: line = EMA(fast) −
//! EMA(slow) (both SMA-seeded on the raw series → line valid from index
//! slow−1); signal = EMA(signal) of the LINE with SMA seeding over the
//! line's first `signal` valid values; histogram = line − signal.

use super::ema::EmaState;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MacdPoint {
    pub line: f64,
    pub signal: f64,
    pub histogram: f64,
}

/// Incremental MACD. O(1) per update.
#[derive(Debug, Clone)]
pub struct MacdState {
    fast: EmaState,
    slow: EmaState,
    signal: EmaState,
}

impl MacdState {
    pub fn new(fast: usize, slow: usize, signal: usize) -> Option<Self> {
        if fast == 0 || slow == 0 || signal == 0 || fast >= slow {
            return None;
        }
        Some(Self {
            fast: EmaState::new(fast)?,
            slow: EmaState::new(slow)?,
            signal: EmaState::new(signal)?,
        })
    }

    /// Feed one close. Line available from index slow−1; full point (with
    /// signal + histogram) from index slow+signal−2.
    pub fn update(&mut self, x: f64) -> (Option<f64>, Option<MacdPoint>) {
        let fast = self.fast.update(x);
        let slow = self.slow.update(x);
        let line = match (fast, slow) {
            (Some(f), Some(s)) => f - s,
            _ => return (None, None),
        };
        match self.signal.update(line) {
            Some(sig) => (
                Some(line),
                Some(MacdPoint {
                    line,
                    signal: sig,
                    histogram: line - sig,
                }),
            ),
            None => (Some(line), None),
        }
    }
}

/// Batch MACD: (line, signal, histogram) vectors, NaN during warmups.
pub fn macd(
    values: &[f64],
    fast: usize,
    slow: usize,
    signal: usize,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = values.len();
    let Some(mut st) = MacdState::new(fast, slow, signal) else {
        return (vec![f64::NAN; n], vec![f64::NAN; n], vec![f64::NAN; n]);
    };
    let mut lines = Vec::with_capacity(n);
    let mut signals = Vec::with_capacity(n);
    let mut hists = Vec::with_capacity(n);
    for &x in values {
        let (line, point) = st.update(x);
        lines.push(line.unwrap_or(f64::NAN));
        match point {
            Some(p) => {
                signals.push(p.signal);
                hists.push(p.histogram);
            }
            None => {
                signals.push(f64::NAN);
                hists.push(f64::NAN);
            }
        }
    }
    (lines, signals, hists)
}
