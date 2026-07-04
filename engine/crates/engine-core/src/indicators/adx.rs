//! ADX / +DI / −DI, pandas-ta 0.4.71b0 pure-python semantics (source-read
//! and numerically verified — this is NOT textbook Wilder):
//!
//! - +DM/−DM from bar 1 (bar 0 has no previous bar): +DM = h−h₋₁ when it
//!   exceeds l₋₁−l and > 0, else 0 (mirror for −DM).
//! - Smoothed DM: `ewm(alpha=1/length, adjust=False)` — pandas seeds with
//!   the FIRST value of the series (bar 1), no warmup masking.
//! - Internal ATR uses `prenan=True`: TR[0] is NaN, so the SMA seed at bar
//!   length−1 averages only length−1 TR samples (bars 1..length−1). This
//!   differs from the standalone ATR (atr.rs), which seeds over `length`
//!   samples including TR[0]=h−l. Both verified against the fixture.
//! - DI± = 100·S±DM/ATRᵢₙₜ — first valid at bar length−1.
//! - DX = 100·|DI⁺−DI⁻|/(DI⁺+DI⁻); ADX = ewm(alpha=1/length, adjust=False)
//!   over DX, seeded with the first DX → ADX[length−1] == DX[length−1].

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AdxPoint {
    pub adx: f64,
    pub plus_di: f64,
    pub minus_di: f64,
}

/// Incremental ADX. O(1) per update after seeding.
#[derive(Debug, Clone)]
pub struct AdxState {
    length: usize,
    alpha: f64,
    prev_hlc: Option<(f64, f64, f64)>,
    bars_seen: usize,
    // ewm-smoothed DM (seeded at bar 1 with the raw first values)
    s_dm_plus: Option<f64>,
    s_dm_minus: Option<f64>,
    // internal ATR with prenan seeding (length−1 samples, bars 1..length−1)
    tr_seed_sum: f64,
    tr_seed_count: usize,
    atr: Option<f64>,
    adx: Option<f64>,
}

impl AdxState {
    pub fn new(length: usize) -> Option<Self> {
        if length < 2 {
            return None;
        }
        Some(Self {
            length,
            alpha: 1.0 / length as f64,
            prev_hlc: None,
            bars_seen: 0,
            s_dm_plus: None,
            s_dm_minus: None,
            tr_seed_sum: 0.0,
            tr_seed_count: 0,
            atr: None,
            adx: None,
        })
    }

    /// Feed one bar; Some(point) from bar index `length-1` onward.
    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<AdxPoint> {
        let bar = self.bars_seen;
        self.bars_seen += 1;

        let Some((ph, pl, pc)) = self.prev_hlc.replace((high, low, close)) else {
            return None; // bar 0: no DM, TR is prenan'd
        };

        let up = high - ph;
        let down = pl - low;
        let dm_plus = if up > down && up > 0.0 { up } else { 0.0 };
        let dm_minus = if down > up && down > 0.0 { down } else { 0.0 };
        let tr = (high - low).max((high - pc).abs()).max((low - pc).abs());

        // ewm(adjust=False) seeded with the series' first value (bar 1)
        self.s_dm_plus = Some(match self.s_dm_plus {
            None => dm_plus,
            Some(p) => self.alpha * dm_plus + (1.0 - self.alpha) * p,
        });
        self.s_dm_minus = Some(match self.s_dm_minus {
            None => dm_minus,
            Some(p) => self.alpha * dm_minus + (1.0 - self.alpha) * p,
        });

        // internal ATR: seed = mean of TR over bars 1..length−1, at bar length−1
        let atr = match self.atr {
            Some(prev) => {
                let next = self.alpha * tr + (1.0 - self.alpha) * prev;
                self.atr = Some(next);
                next
            }
            None => {
                self.tr_seed_sum += tr;
                self.tr_seed_count += 1;
                if bar == self.length - 1 {
                    let seed = self.tr_seed_sum / self.tr_seed_count as f64;
                    self.atr = Some(seed);
                    seed
                } else {
                    return None;
                }
            }
        };

        if atr == 0.0 {
            return None; // 14 zero-range bars: pandas emits inf; we abstain
        }
        let (sp, sm) = match (self.s_dm_plus, self.s_dm_minus) {
            (Some(a), Some(b)) => (a, b),
            _ => return None,
        };
        let plus_di = 100.0 * sp / atr;
        let minus_di = 100.0 * sm / atr;
        let sum_di = plus_di + minus_di;
        let dx = if sum_di == 0.0 {
            0.0
        } else {
            100.0 * (plus_di - minus_di).abs() / sum_di
        };

        let adx = match self.adx {
            Some(prev) => self.alpha * dx + (1.0 - self.alpha) * prev,
            None => dx, // first-DX seed
        };
        self.adx = Some(adx);

        Some(AdxPoint {
            adx,
            plus_di,
            minus_di,
        })
    }
}

/// Batch ADX: (adx, +di, −di) vectors, NaN during warmup.
pub fn adx(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    length: usize,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = high.len().min(low.len()).min(close.len());
    let Some(mut st) = AdxState::new(length) else {
        return (vec![f64::NAN; n], vec![f64::NAN; n], vec![f64::NAN; n]);
    };
    let mut a = Vec::with_capacity(n);
    let mut p = Vec::with_capacity(n);
    let mut m = Vec::with_capacity(n);
    for i in 0..n {
        let (h, l, c) = (
            high.get(i).copied().unwrap_or(f64::NAN),
            low.get(i).copied().unwrap_or(f64::NAN),
            close.get(i).copied().unwrap_or(f64::NAN),
        );
        match st.update(h, l, c) {
            Some(pt) => {
                a.push(pt.adx);
                p.push(pt.plus_di);
                m.push(pt.minus_di);
            }
            None => {
                a.push(f64::NAN);
                p.push(f64::NAN);
                m.push(f64::NAN);
            }
        }
    }
    (a, p, m)
}
