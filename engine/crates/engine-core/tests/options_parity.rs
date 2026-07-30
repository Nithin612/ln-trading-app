//! engine-core options math vs an independent Python Black-Scholes reference
//! (backend/scripts/gen_options_goldens.py). The reference re-implements the
//! same generalized BSM formulas, so this is a tight transcription check
//! (agreement to ~1e-9, limited by Python/Rust libm ULP differences); the
//! reference in turn is pinned to `math.erf` to < 1e-6 at generation time.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use engine_core::options::{greeks, implied_vol, price, Bsm, OptionType};
use serde::Deserialize;

#[derive(Deserialize)]
struct Case {
    spot: f64,
    strike: f64,
    t: f64,
    rate: f64,
    carry: f64,
    vol: f64,
    call: f64,
    put: f64,
    call_delta: f64,
    put_delta: f64,
    gamma: f64,
    vega: f64,
    call_theta: f64,
    put_theta: f64,
    call_rho: f64,
    put_rho: f64,
}

#[derive(Deserialize)]
struct Fixture {
    cases: Vec<Case>,
}

// numpy-allclose style: |got − want| ≤ atol + rtol·|want|.
fn close(got: f64, want: f64, what: &str) {
    let atol = 1e-6;
    let rtol = 1e-8;
    assert!(
        (got - want).abs() <= atol + rtol * want.abs(),
        "{what}: got {got}, want {want} (diff {:e})",
        (got - want).abs()
    );
}

#[test]
fn options_match_python_reference() {
    let raw = include_str!("fixtures/options_reference.json");
    let fixture: Fixture = serde_json::from_str(raw).expect("parse options_reference.json");
    assert!(fixture.cases.len() >= 80, "fixture shrank unexpectedly");

    for c in &fixture.cases {
        let p = Bsm {
            spot: c.spot,
            strike: c.strike,
            t: c.t,
            rate: c.rate,
            carry: c.carry,
            vol: c.vol,
        };
        let tag = format!("S{}/K{} t{} b{} v{}", c.spot, c.strike, c.t, c.carry, c.vol);

        close(
            price(OptionType::Call, &p).unwrap(),
            c.call,
            &format!("{tag} call"),
        );
        close(
            price(OptionType::Put, &p).unwrap(),
            c.put,
            &format!("{tag} put"),
        );

        let cg = greeks(OptionType::Call, &p).unwrap();
        let pg = greeks(OptionType::Put, &p).unwrap();
        close(cg.delta, c.call_delta, &format!("{tag} call.delta"));
        close(pg.delta, c.put_delta, &format!("{tag} put.delta"));
        close(cg.gamma, c.gamma, &format!("{tag} gamma"));
        close(cg.vega, c.vega, &format!("{tag} vega"));
        close(cg.theta, c.call_theta, &format!("{tag} call.theta"));
        close(pg.theta, c.put_theta, &format!("{tag} put.theta"));
        close(cg.rho, c.call_rho, &format!("{tag} call.rho"));
        close(pg.rho, c.put_rho, &format!("{tag} put.rho"));

        // Cross-impl IV: recover vol from the Python-priced premium where the
        // option is vol-sensitive enough to invert (skip the degenerate
        // deep-OTM / near-expiry cases whose premium carries no vega).
        if c.vega > 1.0 {
            let iv = implied_vol(
                OptionType::Call,
                c.call,
                c.spot,
                c.strike,
                c.t,
                c.rate,
                c.carry,
            )
            .unwrap_or_else(|| panic!("{tag}: no IV from call premium"));
            assert!((iv - c.vol).abs() < 1e-4, "{tag} iv {iv} vs {}", c.vol);
        }
    }
}
