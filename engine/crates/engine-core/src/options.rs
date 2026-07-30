//! Black-Scholes–Merton option pricing, Greeks and implied volatility.
//!
//! Phase 4 (F&O analytics). Pure, deterministic f64 math — no I/O, no clocks
//! (`.claude/rules/rust.md`: options math is f64, like the indicator layer).
//! Every entry point returns `Option`: malformed inputs (non-positive spot /
//! strike / time, out-of-arbitrage prices, non-convergence) yield `None`, never
//! a panic or a NaN leaking to the caller.
//!
//! Generalized cost-of-carry `b` selects the model, so one code path serves
//! both instruments the NSE F&O book needs:
//!   * `b = rate`      → Black-Scholes (non-dividend equity/index spot options)
//!   * `b = rate − q`  → Merton (continuous dividend yield `q`)
//!   * `b = 0`         → Black-76 (options on futures / forwards)
//!
//! The normal CDF is Abramowitz & Stegun 26.2.17 (|error| < 7.5e-8). Prices and
//! Greeks are therefore accurate to ~1e-6 relative — far beyond any tradeable
//! precision — which the golden suite pins against an independent `math.erf`
//! reference and hand-computed textbook values.

use std::f64::consts::PI;

/// Call or put.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OptionType {
    Call,
    Put,
}

/// Standard-normal probability density φ(x).
#[must_use]
pub fn norm_pdf(x: f64) -> f64 {
    (-0.5 * x * x).exp() / (2.0 * PI).sqrt()
}

/// Standard-normal cumulative distribution Φ(x), Abramowitz & Stegun 26.2.17.
#[must_use]
pub fn norm_cdf(x: f64) -> f64 {
    // Φ(-x) = 1 − Φ(x); compute on |x| then reflect.
    const B0: f64 = 0.231_641_9;
    const B1: f64 = 0.319_381_530;
    const B2: f64 = -0.356_563_782;
    const B3: f64 = 1.781_477_937;
    const B4: f64 = -1.821_255_978;
    const B5: f64 = 1.330_274_429;

    let ax = x.abs();
    let t = 1.0 / (1.0 + B0 * ax);
    // Horner form of (B1 t + B2 t² + B3 t³ + B4 t⁴ + B5 t⁵).
    let poly = t * (B1 + t * (B2 + t * (B3 + t * (B4 + t * B5))));
    let tail = norm_pdf(ax) * poly; // = 1 − Φ(ax)
    if x >= 0.0 {
        1.0 - tail
    } else {
        tail
    }
}

/// One option's market parameters. `vol` is annualized (0.20 = 20%); `t` is in
/// years; `rate`/`carry` are continuously compounded.
#[derive(Clone, Copy, Debug)]
pub struct Bsm {
    pub spot: f64,
    pub strike: f64,
    pub t: f64,
    pub rate: f64,
    pub carry: f64,
    pub vol: f64,
}

/// The option Greeks. Units: `delta` per ₹1 of spot; `gamma` per ₹1²; `vega`
/// per 1.00 of vol (÷100 for per-1%); `theta` per YEAR (÷365 for per-day);
/// `rho` per 1.00 of rate. `vega`/`theta`/`rho` follow the standard BSM
/// definitions holding `carry` fixed as `rate` varies.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Greeks {
    pub delta: f64,
    pub gamma: f64,
    pub vega: f64,
    pub theta: f64,
    pub rho: f64,
}

// d1, d2 for a well-formed (positive, live, positive-vol) contract.
fn d1_d2(p: &Bsm) -> Option<(f64, f64)> {
    if p.spot <= 0.0 || p.strike <= 0.0 || p.t <= 0.0 || p.vol <= 0.0 {
        return None;
    }
    let vsqrt = p.vol * p.t.sqrt();
    if vsqrt <= 0.0 {
        return None;
    }
    let d1 = ((p.spot / p.strike).ln() + (p.carry + 0.5 * p.vol * p.vol) * p.t) / vsqrt;
    Some((d1, d1 - vsqrt))
}

// Discounted intrinsic on the forward — the limit as vol→0 or t→0.
fn intrinsic(kind: OptionType, p: &Bsm) -> Option<f64> {
    if p.spot <= 0.0 || p.strike <= 0.0 || p.t < 0.0 {
        return None;
    }
    let fwd = p.spot * (p.carry * p.t).exp();
    let disc = (-p.rate * p.t).exp();
    let v = match kind {
        OptionType::Call => (fwd - p.strike).max(0.0),
        OptionType::Put => (p.strike - fwd).max(0.0),
    };
    Some(disc * v)
}

/// Option price under the generalized BSM model. Non-positive vol or time
/// collapse to the discounted intrinsic (the deterministic limit).
#[must_use]
pub fn price(kind: OptionType, p: &Bsm) -> Option<f64> {
    let Some((d1, d2)) = d1_d2(p) else {
        return intrinsic(kind, p);
    };
    let carry_disc = ((p.carry - p.rate) * p.t).exp(); // e^{(b−r)T}
    let rate_disc = (-p.rate * p.t).exp(); // e^{−rT}
    let px = match kind {
        OptionType::Call => {
            p.spot * carry_disc * norm_cdf(d1) - p.strike * rate_disc * norm_cdf(d2)
        }
        OptionType::Put => {
            p.strike * rate_disc * norm_cdf(-d2) - p.spot * carry_disc * norm_cdf(-d1)
        }
    };
    Some(px)
}

/// The five Greeks. `None` for a degenerate contract (non-positive spot /
/// strike / time / vol) where the derivatives are undefined.
#[must_use]
pub fn greeks(kind: OptionType, p: &Bsm) -> Option<Greeks> {
    let (d1, d2) = d1_d2(p)?;
    let carry_disc = ((p.carry - p.rate) * p.t).exp();
    let rate_disc = (-p.rate * p.t).exp();
    let sqrt_t = p.t.sqrt();
    let pdf_d1 = norm_pdf(d1);

    let (delta, theta, rho) = match kind {
        OptionType::Call => {
            let delta = carry_disc * norm_cdf(d1);
            let theta = -p.spot * carry_disc * pdf_d1 * p.vol / (2.0 * sqrt_t)
                - (p.carry - p.rate) * p.spot * carry_disc * norm_cdf(d1)
                - p.rate * p.strike * rate_disc * norm_cdf(d2);
            let rho = p.t * p.strike * rate_disc * norm_cdf(d2);
            (delta, theta, rho)
        }
        OptionType::Put => {
            let delta = carry_disc * (norm_cdf(d1) - 1.0);
            let theta = -p.spot * carry_disc * pdf_d1 * p.vol / (2.0 * sqrt_t)
                + (p.carry - p.rate) * p.spot * carry_disc * norm_cdf(-d1)
                + p.rate * p.strike * rate_disc * norm_cdf(-d2);
            let rho = -p.t * p.strike * rate_disc * norm_cdf(-d2);
            (delta, theta, rho)
        }
    };
    let gamma = carry_disc * pdf_d1 / (p.spot * p.vol * sqrt_t);
    let vega = p.spot * carry_disc * pdf_d1 * sqrt_t;
    Some(Greeks {
        delta,
        gamma,
        vega,
        theta,
        rho,
    })
}

/// Implied volatility from a market price via Newton–Raphson with a
/// Manaster–Koehler seed and a bisection fallback. `None` when the price
/// violates the no-arbitrage bounds or the solver fails to converge.
///
/// `market_price` is the observed premium; the remaining args mirror [`Bsm`]
/// minus `vol`.
#[must_use]
pub fn implied_vol(
    kind: OptionType,
    market_price: f64,
    spot: f64,
    strike: f64,
    t: f64,
    rate: f64,
    carry: f64,
) -> Option<f64> {
    if !market_price.is_finite() || market_price < 0.0 || spot <= 0.0 || strike <= 0.0 || t <= 0.0 {
        return None;
    }
    let at = |vol: f64| Bsm {
        spot,
        strike,
        t,
        rate,
        carry,
        vol,
    };

    // No-arbitrage bounds: price ∈ [intrinsic, upper]. Below intrinsic or above
    // the asset bound has no positive-vol solution.
    let lower = intrinsic(kind, &at(0.0))?;
    let carry_disc = ((carry - rate) * t).exp();
    let upper = match kind {
        OptionType::Call => spot * carry_disc,
        OptionType::Put => strike * (-rate * t).exp(),
    };
    const TOL: f64 = 1e-8;
    if market_price < lower - TOL || market_price > upper + TOL {
        return None;
    }

    // Manaster–Koehler seed.
    let seed = (2.0 * ((spot / strike).ln() + carry * t).abs() / t).sqrt();
    let mut vol = seed.clamp(1e-3, 5.0);

    // Newton–Raphson.
    for _ in 0..100 {
        let p = price(kind, &at(vol))?;
        let diff = p - market_price;
        if diff.abs() < TOL {
            return Some(vol);
        }
        let v = greeks(kind, &at(vol))?.vega;
        if v < 1e-8 {
            break; // vega too flat — hand off to bisection
        }
        let step = diff / v;
        vol = (vol - step).clamp(1e-6, 5.0);
    }

    // Bisection fallback on [1e-6, 5.0]; price is monotone increasing in vol.
    let (mut lo, mut hi) = (1e-6_f64, 5.0_f64);
    let mut plo = price(kind, &at(lo))? - market_price;
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        let pmid = price(kind, &at(mid))? - market_price;
        if pmid.abs() < TOL {
            return Some(mid);
        }
        if (pmid > 0.0) == (plo > 0.0) {
            lo = mid;
            plo = pmid;
        } else {
            hi = mid;
        }
        if (hi - lo) < 1e-9 {
            return Some(0.5 * (lo + hi));
        }
    }
    None
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::panic, clippy::indexing_slicing)]
mod tests {
    use super::*;

    fn bsm(spot: f64, strike: f64, t: f64, rate: f64, carry: f64, vol: f64) -> Bsm {
        Bsm {
            spot,
            strike,
            t,
            rate,
            carry,
            vol,
        }
    }

    // ── Normal CDF ──────────────────────────────────────────────────────────
    #[test]
    fn norm_cdf_anchors() {
        assert!((norm_cdf(0.0) - 0.5).abs() < 1e-9);
        // Symmetry Φ(−x) = 1 − Φ(x).
        for &x in &[0.25, 0.7693, 1.5, 2.33, 3.0] {
            assert!((norm_cdf(-x) - (1.0 - norm_cdf(x))).abs() < 1e-9);
        }
        // Published values (A&S accuracy ~1e-7).
        assert!((norm_cdf(1.0) - 0.841_344_75).abs() < 1e-6);
        assert!((norm_cdf(1.96) - 0.975_002_1).abs() < 1e-6);
        // Bounded in (0, 1).
        assert!(norm_cdf(-8.0) >= 0.0 && norm_cdf(8.0) <= 1.0);
    }

    // ── Hand-computed textbook golden (Hull, Options Futures & Other
    // Derivatives): S=42 K=40 r=10% σ=20% T=0.5 → call 4.76, put 0.81. ───────
    #[test]
    fn hull_textbook_call_and_put() {
        let p = bsm(42.0, 40.0, 0.5, 0.10, 0.10, 0.20);
        let call = price(OptionType::Call, &p).unwrap();
        let put = price(OptionType::Put, &p).unwrap();
        assert!((call - 4.759).abs() < 5e-3, "call {call}");
        assert!((put - 0.808).abs() < 5e-3, "put {put}");
    }

    #[test]
    fn hull_textbook_greeks() {
        let p = bsm(42.0, 40.0, 0.5, 0.10, 0.10, 0.20);
        let g = greeks(OptionType::Call, &p).unwrap();
        assert!((g.delta - 0.779).abs() < 5e-3, "delta {}", g.delta);
        assert!((g.gamma - 0.0500).abs() < 5e-4, "gamma {}", g.gamma);
        assert!((g.vega - 8.813).abs() < 1e-2, "vega {}", g.vega); // per 1.00 vol
    }

    // ── Put–call parity: C − P = S·e^{(b−r)T} − K·e^{−rT}, independent of the
    // CDF, so it must hold tight across the grid. ────────────────────────────
    #[test]
    fn put_call_parity_grid() {
        for &spot in &[80.0, 100.0, 125.0] {
            for &vol in &[0.10, 0.25, 0.60] {
                for &t in &[0.02, 0.25, 1.0] {
                    for &carry in &[0.0, 0.06] {
                        let p = bsm(spot, 100.0, t, 0.06, carry, vol);
                        let c = price(OptionType::Call, &p).unwrap();
                        let pu = price(OptionType::Put, &p).unwrap();
                        let lhs = c - pu;
                        let rhs = spot * ((carry - 0.06) * t).exp() - 100.0 * (-0.06 * t).exp();
                        assert!((lhs - rhs).abs() < 1e-9, "parity {lhs} vs {rhs}");
                    }
                }
            }
        }
    }

    // ── Implied vol round-trips the price it was made from. ──────────────────
    #[test]
    fn implied_vol_round_trip() {
        for &kind in &[OptionType::Call, OptionType::Put] {
            for &vol in &[0.08, 0.20, 0.45, 0.90] {
                for &spot in &[90.0, 100.0, 115.0] {
                    let p = bsm(spot, 100.0, 0.3, 0.06, 0.0, vol);
                    let px = price(kind, &p).unwrap();
                    let iv = implied_vol(kind, px, spot, 100.0, 0.3, 0.06, 0.0)
                        .unwrap_or_else(|| panic!("no IV for {kind:?} vol={vol} spot={spot}"));
                    assert!((iv - vol).abs() < 1e-4, "iv {iv} vs {vol} ({kind:?})");
                }
            }
        }
    }

    #[test]
    fn implied_vol_rejects_out_of_bounds() {
        // Below intrinsic (call, deep ITM) and above the asset bound → None.
        assert!(implied_vol(OptionType::Call, 0.0, 120.0, 100.0, 0.25, 0.06, 0.0).is_none());
        assert!(implied_vol(OptionType::Call, 1e9, 100.0, 100.0, 0.25, 0.06, 0.0).is_none());
        assert!(implied_vol(OptionType::Call, 5.0, 100.0, 100.0, 0.0, 0.06, 0.0).is_none());
        // t<=0
    }

    // ── Greek signs / bounds. ────────────────────────────────────────────────
    #[test]
    fn greek_signs() {
        let p = bsm(100.0, 100.0, 0.5, 0.06, 0.0, 0.25);
        let c = greeks(OptionType::Call, &p).unwrap();
        let pu = greeks(OptionType::Put, &p).unwrap();
        assert!(c.delta > 0.0 && c.delta < 1.0);
        assert!(pu.delta < 0.0 && pu.delta > -1.0);
        assert!(c.gamma > 0.0 && pu.gamma > 0.0);
        assert!(c.vega > 0.0 && pu.vega > 0.0);
        // Call/put share gamma and vega (second-order & vol sensitivity).
        assert!((c.gamma - pu.gamma).abs() < 1e-12);
        assert!((c.vega - pu.vega).abs() < 1e-12);
    }

    // ── Price is monotone increasing in vol (vega > 0). ──────────────────────
    #[test]
    fn price_monotone_in_vol() {
        let mut prev = f64::NEG_INFINITY;
        for i in 1..=50 {
            let vol = f64::from(i) * 0.02;
            let px = price(OptionType::Call, &bsm(100.0, 100.0, 0.4, 0.06, 0.0, vol)).unwrap();
            assert!(px > prev, "not monotone at vol={vol}");
            prev = px;
        }
    }

    // ── Degenerate inputs collapse to intrinsic, never panic. ────────────────
    #[test]
    fn zero_vol_and_expiry_are_intrinsic() {
        // vol = 0 → discounted intrinsic on the forward.
        let p0 = bsm(110.0, 100.0, 0.5, 0.06, 0.0, 0.0);
        let want = (110.0 - 100.0) * (-0.06 * 0.5_f64).exp(); // Black-76 carry=0
        assert!((price(OptionType::Call, &p0).unwrap() - want).abs() < 1e-9);
        // t = 0 → undiscounted intrinsic.
        let pt = bsm(110.0, 100.0, 0.0, 0.06, 0.0, 0.25);
        assert!((price(OptionType::Call, &pt).unwrap() - 10.0).abs() < 1e-9);
    }

    #[test]
    fn non_positive_inputs_return_none_not_panic() {
        assert!(greeks(OptionType::Call, &bsm(0.0, 100.0, 0.5, 0.06, 0.0, 0.25)).is_none());
        assert!(greeks(OptionType::Call, &bsm(100.0, 0.0, 0.5, 0.06, 0.0, 0.25)).is_none());
        assert!(price(OptionType::Call, &bsm(-1.0, 100.0, 0.5, 0.06, 0.0, 0.25)).is_none());
    }
}
