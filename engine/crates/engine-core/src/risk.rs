//! Position sizing + SL/TP placement — faithful port of
//! backend/app/analysis/risk.py (SIGNAL_ENGINE.md §6) and
//! backend/app/signals/classifier.py.
//!
//! Money convention (.claude/rules/rust.md): i64 scaled 1e-4 (matches
//! Numeric(12,4) — sub-paise). Python's `_pct` quantizes to 0.0001 with
//! Decimal's default ROUND_HALF_EVEN — replicated exactly here. f64 prices
//! enter via `money_from_f64`, which parses the shortest decimal repr the
//! way Python's `Decimal(str(x))` does.

pub const MONEY_SCALE: i64 = 10_000; // 1e-4 rupees

/// Money value scaled 1e-4. Plain i64 newtype-by-convention (kept bare for
/// arithmetic ergonomics inside the crate; the FFI layer wraps it).
pub type Money = i64;

/// Exact equivalent of Python `Decimal(str(x))` quantized at 1e-4 —
/// parses the shortest round-trip decimal representation digit-by-digit,
/// then half-even rounds anything beyond 4 decimal places.
pub fn money_from_f64(x: f64) -> Option<Money> {
    if !x.is_finite() {
        return None;
    }
    let s = format!("{x}");
    money_from_str(&s)
}

/// Parse "123.4567", "-0.05", "1e-05"-style strings to scaled 1e-4 with
/// ROUND_HALF_EVEN beyond 4 dp.
pub fn money_from_str(s: &str) -> Option<Money> {
    // Scientific notation falls back to a widened fixed rendering.
    if s.contains(['e', 'E']) {
        let v: f64 = s.parse().ok()?;
        let widened = format!("{v:.10}");
        return money_from_str(&widened);
    }
    let (neg, body) = match s.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, s),
    };
    let (int_part, frac_part) = match body.split_once('.') {
        Some((i, f)) => (i, f),
        None => (body, ""),
    };
    let int_v: i64 = if int_part.is_empty() {
        0
    } else {
        int_part.parse().ok()?
    };

    let mut frac4: i64 = 0;
    for (i, ch) in frac_part.chars().take(4).enumerate() {
        let d = ch.to_digit(10)? as i64;
        frac4 += d * 10_i64.pow(3 - i as u32);
    }
    let mut value = int_v.checked_mul(MONEY_SCALE)?.checked_add(frac4)?;

    // Half-even on the remainder digits
    let rest: Vec<u32> = frac_part
        .chars()
        .skip(4)
        .filter_map(|c| c.to_digit(10))
        .collect();
    if let Some(&first) = rest.first() {
        let round_up = match first {
            0..=4 => false,
            6..=9 => true,
            5 => rest.iter().skip(1).any(|&d| d > 0) || value % 2 == 1,
            _ => false,
        };
        if round_up {
            value = value.checked_add(1)?;
        }
    }
    Some(if neg { -value } else { value })
}

/// §6 formula: floor(capital × risk% / |entry − SL|). risk_pct is a WHOLE
/// percent scaled 1e-4 (2% == 20_000). Returns None when entry == SL
/// (Python raises ValueError).
pub fn compute_quantity(
    capital: Money,
    risk_pct: Money,
    entry: Money,
    stop_loss: Money,
) -> Option<i64> {
    if entry == stop_loss {
        return None;
    }
    // risk_amount = capital * risk_pct / 100  (exact in i128)
    let risk_amount_num = i128::from(capital) * i128::from(risk_pct); // scale 1e-8
    let risk_per_share = i128::from((entry - stop_loss).abs()); // scale 1e-4
                                                                // qty = floor(risk_amount / 100 / risk_per_share)
                                                                //     = floor(capital·risk_pct / (100·SCALE·risk_per_share)) with scales folded
    let denom = risk_per_share * 100 * i128::from(MONEY_SCALE);
    let qty = risk_amount_num / denom; // truncation == floor for non-negative
    i64::try_from(qty.max(0)).ok()
}

/// Python `_pct`: (price × pct / 100).quantize(1e-4, ROUND_HALF_EVEN).
/// pct is scaled 1e-4 (0.30% == 3_000).
fn pct_of(price: Money, pct: Money) -> Money {
    // price(1e-4) × pct(1e-4) / 100 → scale 1e-8/100=1e-10 → to 1e-4: ÷1e6·100 = ÷1e4·100... derive:
    // exact numerator N = price_u * pct_u  (units: 1e-8 of rupee·percent)
    // value_rupees = N / (1e8 * 100); scaled 1e-4 → N / (1e4 * 100) = N / 1_000_000
    let n = i128::from(price) * i128::from(pct);
    div_half_even(n, 1_000_000)
}

fn div_half_even(n: i128, d: i128) -> Money {
    let q = n.div_euclid(d);
    let r = n.rem_euclid(d);
    let double = r * 2;
    let rounded = if double > d || (double == d && q % 2 != 0) {
        q + 1
    } else {
        q
    };
    #[allow(clippy::cast_possible_truncation)]
    {
        rounded as Money
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Classification {
    Scalp,
    Intraday,
    Swing,
    Positional,
}

/// backend/app/signals/classifier.py — exact mapping.
pub fn classify(timeframe: &str, is_multibagger: bool) -> Classification {
    match timeframe {
        "1m" | "5m" => Classification::Scalp,
        "15m" | "1h" => Classification::Intraday,
        "1d" => {
            if is_multibagger {
                Classification::Positional
            } else {
                Classification::Swing
            }
        }
        "1w" => Classification::Positional,
        _ => Classification::Intraday,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

/// §6 SL/TP placement. Returns None when the natural SL violates the
/// classification cap (reject, never clamp). Mirrors risk.py exactly,
/// including which branches use swing levels vs fixed percentages.
#[allow(clippy::too_many_lines)]
pub fn compute_levels(
    side: Side,
    classification: Classification,
    entry: Money,
    swing_low: Option<Money>,
    swing_high: Option<Money>,
    ema20_daily: Option<Money>,
) -> Option<(Money, Money)> {
    let (sl, tp, max_sl_pct): (Money, Money, Money) = match classification {
        Classification::Scalp => {
            let sl_off = pct_of(entry, 3_000); // 0.30%
            let tp_off = pct_of(entry, 4_500); // 0.45% → 1:1.5
            match side {
                Side::Buy => (entry - sl_off, entry + tp_off, 5_000),
                Side::Sell => (entry + sl_off, entry - tp_off, 5_000),
            }
        }
        Classification::Intraday => match side {
            Side::Buy => {
                let sl = swing_low.unwrap_or(entry - pct_of(entry, 3_000));
                (sl, entry + (entry - sl) * 2, 5_000)
            }
            Side::Sell => {
                let sl = swing_high.unwrap_or(entry + pct_of(entry, 3_000));
                (sl, entry - (sl - entry) * 2, 5_000)
            }
        },
        Classification::Swing => match side {
            Side::Buy => {
                let sl = swing_low.unwrap_or(entry - pct_of(entry, 20_000));
                (sl, entry + pct_of(entry, 60_000), 80_000) // 6% target, 8% cap
            }
            Side::Sell => {
                let sl = swing_high.unwrap_or(entry + pct_of(entry, 20_000));
                (sl, entry - pct_of(entry, 60_000), 80_000)
            }
        },
        Classification::Positional => match side {
            Side::Buy => {
                let sl = ema20_daily.unwrap_or(entry - pct_of(entry, 50_000));
                (sl, entry + pct_of(entry, 150_000), 150_000)
            }
            Side::Sell => {
                let sl = ema20_daily.unwrap_or(entry + pct_of(entry, 50_000));
                (sl, entry - pct_of(entry, 150_000), 150_000)
            }
        },
    };

    // Python: positional skips the cap check entirely.
    if classification != Classification::Positional {
        // sl_distance_pct > max_sl_pct  ⟺  |entry−sl|·100·SCALE > max·entry
        // (exact cross-multiplication; Python does 28-digit Decimal division,
        // indistinguishable at 4-dp prices)
        let lhs = i128::from((entry - sl).abs()) * 100 * i128::from(MONEY_SCALE);
        let rhs = i128::from(max_sl_pct) * i128::from(entry);
        if lhs > rhs {
            return None;
        }
    }
    Some((sl, tp))
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    fn m(s: &str) -> Money {
        money_from_str(s).unwrap()
    }

    #[test]
    fn spec_worked_example() {
        // §7: capital ₹100k, 2%, entry 490, SL 482 → qty 250
        let qty = compute_quantity(m("100000"), m("2"), m("490"), m("482"));
        assert_eq!(qty, Some(250));
    }

    #[test]
    fn equal_entry_sl_rejected() {
        assert_eq!(
            compute_quantity(m("100000"), m("2"), m("490"), m("490")),
            None
        );
    }

    #[test]
    fn floors_quantity() {
        // risk 2000, per-share 7.3 → 273.97 → 273
        let qty = compute_quantity(m("100000"), m("2"), m("500"), m("492.7"));
        assert_eq!(qty, Some(273));
    }

    #[test]
    fn money_parsing_matches_python_str() {
        assert_eq!(m("101.005"), 1_010_050);
        assert_eq!(m("0.05"), 500);
        assert_eq!(m("-482"), -4_820_000);
        // half-even beyond 4dp
        assert_eq!(m("1.00005"), 10_000); // .00005 → even → stays 10000
        assert_eq!(m("1.00015"), 10_002); // → rounds to even 2
        assert_eq!(m("1.000151"), 10_002);
    }

    #[test]
    fn scalp_levels_buy() {
        // entry 100: SL 99.70, TP 100.45
        let (sl, tp) =
            compute_levels(Side::Buy, Classification::Scalp, m("100"), None, None, None).unwrap();
        assert_eq!(sl, m("99.70"));
        assert_eq!(tp, m("100.45"));
    }

    #[test]
    fn swing_cap_rejects() {
        // swing low 10% below entry → beyond the 8% cap → reject
        let out = compute_levels(
            Side::Buy,
            Classification::Swing,
            m("100"),
            Some(m("90")),
            None,
            None,
        );
        assert_eq!(out, None);
        // 7.9% below → accepted
        let out2 = compute_levels(
            Side::Buy,
            Classification::Swing,
            m("100"),
            Some(m("92.1")),
            None,
            None,
        );
        assert!(out2.is_some());
    }

    #[test]
    fn classify_mapping() {
        assert_eq!(classify("5m", false), Classification::Scalp);
        assert_eq!(classify("1h", false), Classification::Intraday);
        assert_eq!(classify("1d", false), Classification::Swing);
        assert_eq!(classify("1d", true), Classification::Positional);
        assert_eq!(classify("1w", false), Classification::Positional);
        assert_eq!(classify("3h", false), Classification::Intraday);
    }
}
