//! Exponential moving average, pandas-ta semantics (`sma=True` seeding):
//! outputs NaN for the first `length-1` inputs, the SMA of the first
//! `length` inputs at index `length-1`, then the standard recurrence
//! `y = α·x + (1−α)·y_prev` with `α = 2/(length+1)`.

/// Incremental EMA state. O(1) per update after seeding.
#[derive(Debug, Clone)]
pub struct EmaState {
    alpha: f64,
    length: usize,
    /// Running sum of the first `length` values (seed phase only).
    seed_sum: f64,
    seen: usize,
    value: Option<f64>,
}

impl EmaState {
    /// `length` must be ≥ 1; returns None for length 0 (invalid).
    pub fn new(length: usize) -> Option<Self> {
        if length == 0 {
            return None;
        }
        Some(Self {
            alpha: 2.0 / (length as f64 + 1.0),
            length,
            seed_sum: 0.0,
            seen: 0,
            value: None,
        })
    }

    /// Feed one value; Some(ema) once warmed (from index `length-1` onward).
    pub fn update(&mut self, x: f64) -> Option<f64> {
        match self.value {
            Some(prev) => {
                let next = self.alpha * x + (1.0 - self.alpha) * prev;
                self.value = Some(next);
                Some(next)
            }
            None => {
                self.seed_sum += x;
                self.seen += 1;
                if self.seen == self.length {
                    let sma = self.seed_sum / self.length as f64;
                    self.value = Some(sma);
                    Some(sma)
                } else {
                    None
                }
            }
        }
    }

    /// Current value, if warmed.
    pub fn value(&self) -> Option<f64> {
        self.value
    }
}

/// Batch EMA over a slice; NaN during warmup. Built on the incremental
/// state so batch and live paths cannot diverge.
pub fn ema(values: &[f64], length: usize) -> Vec<f64> {
    let Some(mut state) = EmaState::new(length) else {
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

    // Reference values generated from pandas-ta 0.4.71b0:
    //   ta.ema(close, length=5) on the 20-point series below.
    const CLOSE: [f64; 20] = [
        100.0, 101.5, 99.8, 102.3, 103.1, 102.7, 104.2, 105.0, 104.1, 106.3, 107.2, 106.8, 108.5,
        109.1, 108.2, 110.4, 111.0, 110.2, 112.5, 113.1,
    ];
    const EXPECTED_EMA5: [f64; 20] = [
        f64::NAN,
        f64::NAN,
        f64::NAN,
        f64::NAN,
        101.34,
        101.793333333333,
        102.595555555556,
        103.397037037037,
        103.631358024691,
        104.520905349794,
        105.413936899863,
        105.875957933242,
        106.750638622161,
        107.533759081441,
        107.755839387627,
        108.637226258418,
        109.424817505612,
        109.683211670408,
        110.622141113605,
        111.448094075737,
    ];

    #[test]
    fn matches_pandas_ta_reference() {
        let out = ema(&CLOSE, 5);
        for (got, want) in out.iter().zip(EXPECTED_EMA5.iter()) {
            if want.is_nan() {
                assert!(got.is_nan(), "expected NaN warmup, got {got}");
            } else {
                assert_relative_eq!(got, want, max_relative = 1e-9);
            }
        }
    }

    #[test]
    fn incremental_equals_batch() {
        let mut state = match EmaState::new(5) {
            Some(s) => s,
            None => unreachable!("length 5 is valid"),
        };
        let batch = ema(&CLOSE, 5);
        for (i, &x) in CLOSE.iter().enumerate() {
            let inc = state.update(x).unwrap_or(f64::NAN);
            let b = batch.get(i).copied().unwrap_or(f64::NAN);
            assert!(
                (inc.is_nan() && b.is_nan()) || inc == b,
                "diverged at {i}: {inc} vs {b}"
            );
        }
    }

    #[test]
    fn zero_length_is_invalid() {
        assert!(EmaState::new(0).is_none());
        assert!(ema(&CLOSE, 0).iter().all(|v| v.is_nan()));
    }

    #[test]
    fn ema_stays_within_input_bounds() {
        // Property: a convex combination of inputs never escapes their range.
        let out = ema(&CLOSE, 5);
        let (min, max) = CLOSE
            .iter()
            .fold((f64::INFINITY, f64::NEG_INFINITY), |(lo, hi), &v| {
                (lo.min(v), hi.max(v))
            });
        for v in out.iter().filter(|v| !v.is_nan()) {
            assert!(*v >= min && *v <= max, "{v} outside [{min}, {max}]");
        }
    }
}
