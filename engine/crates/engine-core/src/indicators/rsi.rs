//! Relative Strength Index, pandas-ta 0.4.71b0 semantics.
//!
//! Decoded from the reference implementation (verified by hand against its
//! outputs): Wilder smoothing as `ewm(alpha=1/length, adjust=False)` where
//! the smoothed gain/loss series are SEEDED with the FIRST diff — so output
//! begins at index 1, not after `length` bars. RSI = 100·RS/(1+RS) with
//! RS = avg_gain/avg_loss; avg_loss == 0 → 100 (mirrors pandas inf→100),
//! both zero → NaN (0/0 in pandas).

/// Incremental RSI state. O(1) per update.
#[derive(Debug, Clone)]
pub struct RsiState {
    alpha: f64,
    prev: Option<f64>,
    avg_gain: Option<f64>,
    avg_loss: Option<f64>,
}

impl RsiState {
    /// `length` must be ≥ 1.
    pub fn new(length: usize) -> Option<Self> {
        if length == 0 {
            return None;
        }
        Some(Self {
            alpha: 1.0 / length as f64,
            prev: None,
            avg_gain: None,
            avg_loss: None,
        })
    }

    /// Feed one close; Some(rsi) from the second value onward.
    pub fn update(&mut self, x: f64) -> Option<f64> {
        let Some(prev) = self.prev else {
            self.prev = Some(x);
            return None;
        };
        self.prev = Some(x);

        let diff = x - prev;
        let gain = diff.max(0.0);
        let loss = (-diff).max(0.0);

        let (ag, al) = match (self.avg_gain, self.avg_loss) {
            (Some(pg), Some(pl)) => (
                self.alpha * gain + (1.0 - self.alpha) * pg,
                self.alpha * loss + (1.0 - self.alpha) * pl,
            ),
            // Seeded with the first diff — pandas-ta 0.4.x behavior.
            _ => (gain, loss),
        };
        self.avg_gain = Some(ag);
        self.avg_loss = Some(al);

        Some(rsi_from_averages(ag, al))
    }

    /// Current value, if any input has produced one.
    pub fn value(&self) -> Option<f64> {
        match (self.avg_gain, self.avg_loss) {
            (Some(ag), Some(al)) => Some(rsi_from_averages(ag, al)),
            _ => None,
        }
    }
}

fn rsi_from_averages(avg_gain: f64, avg_loss: f64) -> f64 {
    if avg_loss == 0.0 {
        if avg_gain == 0.0 {
            f64::NAN // flat series: pandas yields 0/0
        } else {
            100.0
        }
    } else {
        let rs = avg_gain / avg_loss;
        100.0 * rs / (1.0 + rs)
    }
}

/// Batch RSI over a slice; NaN at index 0 (and for flat prefixes).
pub fn rsi(values: &[f64], length: usize) -> Vec<f64> {
    let Some(mut state) = RsiState::new(length) else {
        return vec![f64::NAN; values.len()];
    };
    values
        .iter()
        .map(|&x| state.update(x).unwrap_or(f64::NAN))
        .collect()
}

#[cfg(test)]
#[allow(clippy::indexing_slicing)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    // Reference values from pandas-ta 0.4.71b0: ta.rsi(close, length=14).
    const CLOSE: [f64; 20] = [
        100.0, 101.5, 99.8, 102.3, 103.1, 102.7, 104.2, 105.0, 104.1, 106.3, 107.2, 106.8, 108.5,
        109.1, 108.2, 110.4, 111.0, 110.2, 112.5, 113.1,
    ];
    const EXPECTED_RSI14: [f64; 20] = [
        f64::NAN,
        100.0,
        91.981132075472,
        92.884739214424,
        93.150717589281,
        91.31273437191,
        91.953881514926,
        92.281082368724,
        87.948054832335,
        89.273880045022,
        89.769697829072,
        87.826543008596,
        88.923877441549,
        89.290795678657,
        84.755304004815,
        86.5533348067,
        87.003546198009,
        83.012657420028,
        85.125203690168,
        85.627344924321,
    ];

    #[test]
    fn matches_pandas_ta_reference() {
        let out = rsi(&CLOSE, 14);
        for (i, (got, want)) in out.iter().zip(EXPECTED_RSI14.iter()).enumerate() {
            if want.is_nan() {
                assert!(got.is_nan(), "index {i}: expected NaN, got {got}");
            } else {
                // Wilder family tolerance tier (1e-6 relative per rules/rust.md)
                assert_relative_eq!(got, want, max_relative = 1e-6);
            }
        }
    }

    #[test]
    fn bounded_zero_to_hundred() {
        let out = rsi(&CLOSE, 14);
        for v in out.iter().filter(|v| !v.is_nan()) {
            assert!((0.0..=100.0).contains(v), "RSI {v} out of [0,100]");
        }
    }

    #[test]
    fn monotonic_up_series_saturates_at_100() {
        let up: Vec<f64> = (0..30).map(|i| 100.0 + f64::from(i)).collect();
        let out = rsi(&up, 14);
        let last = out.last().copied().unwrap_or(f64::NAN);
        assert_relative_eq!(last, 100.0, max_relative = 1e-12);
    }

    #[test]
    fn flat_series_is_nan() {
        let flat = [50.0; 10];
        let out = rsi(&flat, 14);
        assert!(out.iter().skip(1).all(|v| v.is_nan()));
    }
}
