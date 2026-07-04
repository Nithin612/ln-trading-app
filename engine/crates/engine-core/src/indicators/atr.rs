//! Average True Range, pandas-ta 0.4.71b0 semantics (numerically decoded):
//! TR[0] = high−low (no previous close); TR[i] = max(h−l, |h−c₋₁|, |l−c₋₁|).
//! Wilder classic smoothing with SMA SEED: ATR[length−1] = SMA(TR[0..length]),
//! then ATR = (ATR₋₁·(length−1) + TR) / length. Verified to 12 digits
//! against the reference at indices 13/14/20.

/// Incremental ATR. O(1) per update after seeding.
#[derive(Debug, Clone)]
pub struct AtrState {
    length: usize,
    prev_close: Option<f64>,
    seed_sum: f64,
    seen: usize,
    value: Option<f64>,
}

impl AtrState {
    pub fn new(length: usize) -> Option<Self> {
        if length == 0 {
            return None;
        }
        Some(Self {
            length,
            prev_close: None,
            seed_sum: 0.0,
            seen: 0,
            value: None,
        })
    }

    /// Feed one bar; Some(atr) from index `length-1` onward.
    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let tr = match self.prev_close {
            None => high - low,
            Some(pc) => (high - low).max((high - pc).abs()).max((low - pc).abs()),
        };
        self.prev_close = Some(close);

        match self.value {
            Some(prev) => {
                let next = (prev * (self.length as f64 - 1.0) + tr) / self.length as f64;
                self.value = Some(next);
                Some(next)
            }
            None => {
                self.seed_sum += tr;
                self.seen += 1;
                if self.seen == self.length {
                    let seed = self.seed_sum / self.length as f64;
                    self.value = Some(seed);
                    Some(seed)
                } else {
                    None
                }
            }
        }
    }

    pub fn value(&self) -> Option<f64> {
        self.value
    }
}

/// Batch ATR over OHLC arrays (equal lengths assumed; extra tail ignored).
pub fn atr(high: &[f64], low: &[f64], close: &[f64], length: usize) -> Vec<f64> {
    let n = high.len().min(low.len()).min(close.len());
    let Some(mut st) = AtrState::new(length) else {
        return vec![f64::NAN; n];
    };
    (0..n)
        .map(|i| {
            let (h, l, c) = (
                high.get(i).copied().unwrap_or(f64::NAN),
                low.get(i).copied().unwrap_or(f64::NAN),
                close.get(i).copied().unwrap_or(f64::NAN),
            );
            st.update(h, l, c).unwrap_or(f64::NAN)
        })
        .collect()
}
