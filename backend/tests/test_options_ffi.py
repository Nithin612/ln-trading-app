"""tradecore options FFI (Phase 4 slice 4.2b) — the PyO3 face of
engine-core/src/options.rs. Formula correctness is proven on the Rust side;
this pins the batch boundary: shapes, kind parsing, None propagation, errors.

Requires the wheel built (`make engine-build`). Skips cleanly if absent so the
suite still runs on a machine without the compiled extension.
"""

import math

import pytest

tradecore = pytest.importorskip("tradecore")


def test_price_matches_hull_textbook() -> None:
    # S=42 K=40 r=10% carry=10% (equity BS) σ=20% T=0.5 → call 4.76, put 0.81.
    row = (42.0, 40.0, 0.5, 0.10, 0.10, 0.20)
    call = tradecore.option_price("call", [row])[0]
    put = tradecore.option_price("put", [row])[0]
    assert abs(call - 4.759) < 5e-3
    assert abs(put - 0.808) < 5e-3


def test_greeks_shape_and_values() -> None:
    g = tradecore.option_greeks("CE", [(42.0, 40.0, 0.5, 0.10, 0.10, 0.20)])[0]
    delta, gamma, vega, theta, rho = g
    assert abs(delta - 0.779) < 5e-3
    assert abs(gamma - 0.0500) < 5e-4
    assert abs(vega - 8.813) < 1e-2


def test_black76_rho_is_minus_t_price() -> None:
    # carry=0 (options on futures) → rho = −T·price.
    row_price = (100.0, 100.0, 0.5, 0.06, 0.0, 0.25)
    px = tradecore.option_price("call", [row_price])[0]
    rho = tradecore.option_greeks("call", [row_price])[0][4]
    assert abs(rho - (-0.5 * px)) < 1e-9


def test_implied_vol_round_trip_batch() -> None:
    rows_price = [(100.0, 100.0, 0.3, 0.06, 0.0, v) for v in (0.12, 0.25, 0.55)]
    prices = tradecore.option_price("call", rows_price)
    iv_rows = [(p, 100.0, 100.0, 0.3, 0.06, 0.0) for p in prices]
    ivs = tradecore.implied_vol("call", iv_rows)
    for iv, v in zip(ivs, (0.12, 0.25, 0.55), strict=True):
        assert iv is not None and abs(iv - v) < 1e-4


def test_none_propagation() -> None:
    # Degenerate contract → None price; out-of-bounds premium → None IV.
    assert tradecore.option_price("call", [(0.0, 100.0, 0.5, 0.06, 0.0, 0.25)])[0] is None
    assert tradecore.implied_vol("call", [(1e9, 100.0, 100.0, 0.25, 0.06, 0.0)])[0] is None


def test_bad_kind_raises() -> None:
    with pytest.raises(ValueError):
        tradecore.option_price("banana", [(1.0, 1.0, 1.0, 0.0, 0.0, 0.1)])


def test_empty_batch_is_empty() -> None:
    assert tradecore.option_price("put", []) == []
    assert tradecore.implied_vol("put", []) == []


def test_put_call_parity_via_ffi() -> None:
    row = (108.0, 100.0, 0.4, 0.06, 0.06, 0.3)  # carry=rate (equity)
    c = tradecore.option_price("call", [row])[0]
    p = tradecore.option_price("put", [row])[0]
    s, k, t, r, b, _ = row
    parity = s * math.exp((b - r) * t) - k * math.exp(-r * t)
    assert abs((c - p) - parity) < 1e-9
