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

#[cfg(test)]
#[allow(clippy::indexing_slicing)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    // ── T14 — external hand-computed anchor ──────────────────────────────────────────────
    // ATR is anchored elsewhere only through golden fixtures generated from pandas-ta (the
    // chain Rust ← Python ← pandas-ta is self-referential). This pins values derived
    // INDEPENDENTLY of pandas-ta — the documented recursion worked out by hand on a short
    // series (n=3): TR[0]=h−l; TR[i]=max(h−l, |h−c₋₁|, |l−c₋₁|); ATR seeds as SMA(TR[0..n]) at
    // index n−1, then ATR=(ATR₋₁·(n−1)+TR)/n.
    //
    //   H = [10.5, 11.2, 11.0, 11.8, 12.1, 11.6]
    //   L = [10.0, 10.4, 10.3, 11.1, 11.4, 11.0]
    //   C = [10.2, 11.0, 10.6, 11.6, 11.7, 11.2]
    //   TR: [0.5, max(0.8,1.0,0.2)=1.0, max(0.7,0.0,0.7)=0.7, max(0.7,1.2,0.5)=1.2,
    //        max(0.7,0.5,0.2)=0.7, max(0.6,0.1,0.7)=0.7]
    //   seed ATR[2] = (0.5+1.0+0.7)/3 = 0.73333…; ATR[3] = (0.73333…·2 + 1.2)/3 = 0.88888…
    #[test]
    fn hand_computed_reference_anchor() {
        let high = [10.5, 11.2, 11.0, 11.8, 12.1, 11.6];
        let low = [10.0, 10.4, 10.3, 11.1, 11.4, 11.0];
        let close = [10.2, 11.0, 10.6, 11.6, 11.7, 11.2];
        let expected = [
            f64::NAN,
            f64::NAN,
            0.7333333333333331,
            0.888888888888889,
            0.8259259259259256,
            0.7839506172839501,
        ];
        let out = atr(&high, &low, &close, 3);
        assert_eq!(out.len(), expected.len());
        for (i, (got, want)) in out.iter().zip(expected.iter()).enumerate() {
            if want.is_nan() {
                assert!(got.is_nan(), "index {i}: expected NaN, got {got}");
            } else {
                assert_relative_eq!(got, want, max_relative = 1e-9);
            }
        }
    }

    #[test]
    fn warmup_is_nan_and_atr_is_nonnegative() {
        let high = [2.0, 3.0, 2.5, 4.0, 3.5];
        let low = [1.0, 1.5, 1.8, 2.0, 2.2];
        let close = [1.5, 2.5, 2.0, 3.5, 3.0];
        let out = atr(&high, &low, &close, 3);
        assert!(out[0].is_nan() && out[1].is_nan());
        for v in out.iter().filter(|v| !v.is_nan()) {
            assert!(*v >= 0.0, "ATR {v} is negative");
        }
    }
}
