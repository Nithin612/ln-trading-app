//! Bollinger Bands(length, k): middle = SMA(length), bands = mid ± k·σ
//! where σ is the SAMPLE standard deviation (ddof=1 — verified against
//! pandas-ta to 12 digits). Ring-buffer window; σ recomputed per emit
//! (O(length), deterministic, no incremental-variance drift).

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BbandsPoint {
    pub lower: f64,
    pub middle: f64,
    pub upper: f64,
}

#[derive(Debug, Clone)]
pub struct BbandsState {
    buf: Vec<f64>,
    pos: usize,
    filled: bool,
    k: f64,
}

impl BbandsState {
    pub fn new(length: usize, k: f64) -> Option<Self> {
        if length < 2 || !k.is_finite() || k <= 0.0 {
            return None; // ddof=1 needs ≥2 samples
        }
        Some(Self {
            buf: vec![0.0; length],
            pos: 0,
            filled: false,
            k,
        })
    }

    pub fn update(&mut self, x: f64) -> Option<BbandsPoint> {
        if let Some(slot) = self.buf.get_mut(self.pos) {
            *slot = x;
        }
        self.pos += 1;
        if self.pos == self.buf.len() {
            self.pos = 0;
            self.filled = true;
        }
        if !self.filled {
            return None;
        }
        let n = self.buf.len() as f64;
        let mean = self.buf.iter().sum::<f64>() / n;
        let var = self
            .buf
            .iter()
            .map(|v| (v - mean) * (v - mean))
            .sum::<f64>()
            / (n - 1.0);
        let sd = var.sqrt();
        Some(BbandsPoint {
            lower: mean - self.k * sd,
            middle: mean,
            upper: mean + self.k * sd,
        })
    }
}

/// Batch BBands: (lower, middle, upper), NaN during warmup.
pub fn bbands(values: &[f64], length: usize, k: f64) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = values.len();
    let Some(mut st) = BbandsState::new(length, k) else {
        return (vec![f64::NAN; n], vec![f64::NAN; n], vec![f64::NAN; n]);
    };
    let mut lo = Vec::with_capacity(n);
    let mut mid = Vec::with_capacity(n);
    let mut up = Vec::with_capacity(n);
    for &x in values {
        match st.update(x) {
            Some(p) => {
                lo.push(p.lower);
                mid.push(p.middle);
                up.push(p.upper);
            }
            None => {
                lo.push(f64::NAN);
                mid.push(f64::NAN);
                up.push(f64::NAN);
            }
        }
    }
    (lo, mid, up)
}
