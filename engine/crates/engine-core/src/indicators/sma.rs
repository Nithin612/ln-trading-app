//! Simple moving average (rolling mean), NaN during warmup — pandas
//! `rolling(length).mean()` semantics. Ring-buffer incremental state.

/// Incremental SMA over a fixed window. O(1) per update.
#[derive(Debug, Clone)]
pub struct SmaState {
    buf: Vec<f64>,
    pos: usize,
    filled: bool,
    sum: f64,
}

impl SmaState {
    pub fn new(length: usize) -> Option<Self> {
        if length == 0 {
            return None;
        }
        Some(Self {
            buf: vec![0.0; length],
            pos: 0,
            filled: false,
            sum: 0.0,
        })
    }

    pub fn update(&mut self, x: f64) -> Option<f64> {
        // One slot access does both: evict the outgoing value (when filled)
        // and store the incoming one.
        if let Some(slot) = self.buf.get_mut(self.pos) {
            self.sum += if self.filled { x - *slot } else { x };
            *slot = x;
        }
        self.pos += 1;
        if self.pos == self.buf.len() {
            self.pos = 0;
            self.filled = true;
        }
        if self.filled {
            Some(self.sum / self.buf.len() as f64)
        } else {
            None
        }
    }

    pub fn value(&self) -> Option<f64> {
        if self.filled {
            Some(self.sum / self.buf.len() as f64)
        } else {
            None
        }
    }
}

/// Batch SMA; NaN for the first `length-1` outputs.
pub fn sma(values: &[f64], length: usize) -> Vec<f64> {
    let Some(mut state) = SmaState::new(length) else {
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

    #[test]
    fn simple_window() {
        let out = sma(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);
        assert!(out[0].is_nan() && out[1].is_nan());
        assert_eq!(out[2], 2.0);
        assert_eq!(out[3], 3.0);
        assert_eq!(out[4], 4.0);
    }

    #[test]
    fn incremental_matches_batch_on_long_series() {
        let xs: Vec<f64> = (0..100).map(|i| ((i * 37) % 91) as f64 * 0.5).collect();
        let batch = sma(&xs, 20);
        let mut st = match SmaState::new(20) {
            Some(s) => s,
            None => unreachable!(),
        };
        for (i, &x) in xs.iter().enumerate() {
            let inc = st.update(x).unwrap_or(f64::NAN);
            let b = batch.get(i).copied().unwrap_or(f64::NAN);
            assert!((inc.is_nan() && b.is_nan()) || (inc - b).abs() < 1e-12);
        }
    }
}
