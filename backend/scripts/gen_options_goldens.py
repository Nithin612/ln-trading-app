#!/usr/bin/env python3
"""Generate the options-math golden fixture for the Rust parity test.

Independent reference for engine-core/src/options.rs. It re-implements the same
generalized Black-Scholes-Merton formulas in Python and emits a grid of prices
and Greeks to:

    engine/crates/engine-core/tests/fixtures/options_reference.json

Two layers of trust:
  1. This reference uses the SAME Abramowitz-Stegun 26.2.17 normal CDF as Rust,
     so the Rust parity test is a tight transcription check (agreement to ~1e-9,
     limited only by libm ULP differences between Python and Rust).
  2. Before emitting anything, it ASSERTS that the A&S CDF matches the exact
     math.erf-based normal CDF to < 1e-6 across x in [-6, 6] — proving the
     approximation itself is sound, not merely self-consistent with Rust.

Run: `cd backend && uv run python scripts/gen_options_goldens.py`
(Deterministic — no RNG, no network. Re-run only when options.rs formulas or
the grid change; commit the regenerated JSON in the same change.)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

_SQRT_2PI = math.sqrt(2.0 * math.pi)

# A&S 26.2.17 coefficients — identical to engine-core/src/options.rs.
_B0, _B1, _B2, _B3, _B4, _B5 = (
    0.2316419,
    0.319381530,
    -0.356563782,
    1.781477937,
    -1.821255978,
    1.330274429,
)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def norm_cdf(x: float) -> float:
    ax = abs(x)
    t = 1.0 / (1.0 + _B0 * ax)
    poly = t * (_B1 + t * (_B2 + t * (_B3 + t * (_B4 + t * _B5))))
    tail = norm_pdf(ax) * poly
    return 1.0 - tail if x >= 0.0 else tail


def norm_cdf_exact(x: float) -> float:
    """True normal CDF via the error function — the independent oracle."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(spot, strike, t, rate, carry, vol):
    vsqrt = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (carry + 0.5 * vol * vol) * t) / vsqrt
    return d1, d1 - vsqrt


def price(kind: str, spot, strike, t, rate, carry, vol) -> float:
    d1, d2 = _d1_d2(spot, strike, t, rate, carry, vol)
    carry_disc = math.exp((carry - rate) * t)
    rate_disc = math.exp(-rate * t)
    if kind == "call":
        return spot * carry_disc * norm_cdf(d1) - strike * rate_disc * norm_cdf(d2)
    return strike * rate_disc * norm_cdf(-d2) - spot * carry_disc * norm_cdf(-d1)


def greeks(kind: str, spot, strike, t, rate, carry, vol) -> dict[str, float]:
    d1, d2 = _d1_d2(spot, strike, t, rate, carry, vol)
    carry_disc = math.exp((carry - rate) * t)
    rate_disc = math.exp(-rate * t)
    sqrt_t = math.sqrt(t)
    pdf_d1 = norm_pdf(d1)
    gamma = carry_disc * pdf_d1 / (spot * vol * sqrt_t)
    vega = spot * carry_disc * pdf_d1 * sqrt_t
    if kind == "call":
        delta = carry_disc * norm_cdf(d1)
        theta = (
            -spot * carry_disc * pdf_d1 * vol / (2.0 * sqrt_t)
            - (carry - rate) * spot * carry_disc * norm_cdf(d1)
            - rate * strike * rate_disc * norm_cdf(d2)
        )
        rho = t * strike * rate_disc * norm_cdf(d2)
    else:
        delta = carry_disc * (norm_cdf(d1) - 1.0)
        theta = (
            -spot * carry_disc * pdf_d1 * vol / (2.0 * sqrt_t)
            + (carry - rate) * spot * carry_disc * norm_cdf(-d1)
            + rate * strike * rate_disc * norm_cdf(-d2)
        )
        rho = -t * strike * rate_disc * norm_cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def _assert_cdf_accurate() -> float:
    worst = 0.0
    x = -6.0
    while x <= 6.0001:
        worst = max(worst, abs(norm_cdf(x) - norm_cdf_exact(x)))
        x += 0.01
    if worst >= 1e-6:
        raise SystemExit(f"A&S normal CDF too inaccurate vs erf: max err {worst:.2e}")
    return worst


def main() -> None:
    worst = _assert_cdf_accurate()

    rate = 0.06
    grid = []
    # moneyness (spot at strike 100), vol, tenor (yrs), carry (0=Black-76, rate=BS)
    for spot in (80.0, 92.0, 100.0, 108.0, 125.0):
        for vol in (0.12, 0.25, 0.55):
            for t in (0.02, 0.25, 1.0):
                for carry in (0.0, rate):
                    case = {
                        "spot": spot,
                        "strike": 100.0,
                        "t": t,
                        "rate": rate,
                        "carry": carry,
                        "vol": vol,
                        "call": price("call", spot, 100.0, t, rate, carry, vol),
                        "put": price("put", spot, 100.0, t, rate, carry, vol),
                    }
                    cg = greeks("call", spot, 100.0, t, rate, carry, vol)
                    pg = greeks("put", spot, 100.0, t, rate, carry, vol)
                    case.update(
                        {
                            "call_delta": cg["delta"],
                            "put_delta": pg["delta"],
                            "gamma": cg["gamma"],
                            "vega": cg["vega"],
                            "call_theta": cg["theta"],
                            "put_theta": pg["theta"],
                            "call_rho": cg["rho"],
                            "put_rho": pg["rho"],
                        }
                    )
                    grid.append(case)

    out = (
        Path(__file__).resolve().parents[2]
        / "engine/crates/engine-core/tests/fixtures/options_reference.json"
    )
    payload = {
        "note": "Generated by backend/scripts/gen_options_goldens.py — A&S 26.2.17 "
        f"CDF (max err vs erf {worst:.2e}). Do not hand-edit.",
        "cases": grid,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {len(grid)} cases to {out}")
    print(f"A&S CDF max error vs math.erf: {worst:.2e}")


if __name__ == "__main__":
    main()
