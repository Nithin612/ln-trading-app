//! Swing pivot detection — the ONE implementation shared by Dow trend,
//! S/R levels, and swing-level SL placement (the Python code repeats this
//! loop in three places with different `n`; semantics are identical and
//! must stay identical).
//!
//! Python parity: a pivot high at i satisfies
//! `highs[i] == max(highs[i-n ..= i+n])` — plateau ties COUNT as pivots
//! (== comparison, not strict >). First/last n bars can never be pivots.

/// Indices of swing highs over `values` with wing size `n`.
pub fn swing_high_indices(values: &[f64], n: usize) -> Vec<usize> {
    pivot_indices(values, n, true)
}

/// Indices of swing lows.
pub fn swing_low_indices(values: &[f64], n: usize) -> Vec<usize> {
    pivot_indices(values, n, false)
}

fn pivot_indices(values: &[f64], n: usize, want_high: bool) -> Vec<usize> {
    let len = values.len();
    if n == 0 || len < 2 * n + 1 {
        return Vec::new();
    }
    let mut out = Vec::new();
    for i in n..(len - n) {
        let Some(&center) = values.get(i) else {
            continue;
        };
        let Some(window) = values.get(i - n..=i + n) else {
            continue;
        };
        let extreme = window.iter().copied().fold(
            if want_high {
                f64::NEG_INFINITY
            } else {
                f64::INFINITY
            },
            |a, b| {
                if want_high {
                    a.max(b)
                } else {
                    a.min(b)
                }
            },
        );
        if center == extreme {
            out.push(i);
        }
    }
    out
}

#[cfg(test)]
#[allow(clippy::indexing_slicing)]
mod tests {
    use super::*;

    #[test]
    fn finds_obvious_pivots() {
        //            0    1    2     3    4    5     6
        let hs = [1.0, 2.0, 5.0, 2.0, 1.0, 4.0, 1.0];
        assert_eq!(swing_high_indices(&hs, 2), vec![2]);
        let ls = [5.0, 4.0, 1.0, 4.0, 5.0, 2.0, 5.0];
        assert_eq!(swing_low_indices(&ls, 2), vec![2]);
    }

    #[test]
    fn plateau_ties_count() {
        let hs = [1.0, 3.0, 3.0, 3.0, 1.0];
        // indices 1,2,3 all equal the window max for n=1
        assert_eq!(swing_high_indices(&hs, 1), vec![1, 2, 3]);
    }

    #[test]
    fn edges_excluded() {
        // Monotonic rise: the global max sits at the last index, which can
        // never be a pivot (needs n bars on BOTH sides).
        let hs = [1.0, 2.0, 3.0, 4.0, 5.0];
        assert!(swing_high_indices(&hs, 1).is_empty());
        // And an interior plateau IS a pivot per Python == semantics.
        assert_eq!(swing_high_indices(&[9.0, 1.0, 1.0, 1.0, 9.0], 1), vec![2]);
    }
}
