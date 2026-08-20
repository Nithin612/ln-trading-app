"""Sector / index relative-strength overlay (MCE slice 1) — pure guard logic.

The overlay reuses ``eval_relative_strength``'s definition: excess = stock_return −
benchmark_return over ``lookback`` sessions; BUY wants out-performance, SELL wants
under-performance. It is unwired (off) in slice 1, so these are pure-module tests only —
values, both sides, every fail-open branch, and mode gating."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from app.signals import sector_rs as rs

D = Decimal

# lookback=3 ⇒ need = 4 bars. Hand-computable returns off the first/last bar.
STOCK_UP10 = [D(100), D(101), D(105), D(110)]  # 100→110 ⇒ +10%
BENCH_UP5 = [D(100), D(102), D(103), D(105)]  # 100→105 ⇒ +5%
STOCK_UP2 = [D(100), D(101), D("101.5"), D(102)]  # +2%


def _ev(stock, bench, side, *, lookback=3, min_excess="0", label="NIFTY50"):
    return rs.evaluate(
        stock_closes=stock,
        benchmark_closes=bench,
        side=side,
        lookback=lookback,
        min_excess_pct=D(min_excess),
        benchmark_label=label,
    )


def test_long_outperforming_is_eligible_with_exact_excess() -> None:
    v = _ev(STOCK_UP10, BENCH_UP5, "BUY")
    assert v.stock_ret_pct == D(10)
    assert v.bench_ret_pct == D(5)
    assert v.excess_pct == D(5)  # +10 − +5
    assert v.has_benchmark is True
    assert v.side == "LONG"
    assert v.blocked is False
    assert v.reasons == []


def test_long_underperforming_is_blocked() -> None:
    v = _ev(STOCK_UP2, BENCH_UP5, "BUY")
    assert v.excess_pct == D(-3)  # +2 − +5
    assert v.blocked is True
    assert v.reasons and "under-performs" in v.reasons[0]


def test_sell_underperforming_is_eligible() -> None:
    # A short wants the stock weaker than the benchmark ⇒ negative excess passes.
    v = _ev(STOCK_UP2, BENCH_UP5, "SELL")
    assert v.side == "SHORT"
    assert v.excess_pct == D(-3)
    assert v.blocked is False


def test_sell_outperforming_is_blocked() -> None:
    v = _ev(STOCK_UP10, BENCH_UP5, "SELL")
    assert v.excess_pct == D(5)
    assert v.blocked is True
    assert v.reasons and "out-performs" in v.reasons[0]


def test_min_excess_threshold_boundary_passes_on_equality() -> None:
    # excess == min_excess ⇒ LONG passes (the definition uses ≥).
    v = _ev(STOCK_UP10, BENCH_UP5, "BUY", min_excess="5")
    assert v.excess_pct == D(5)
    assert v.blocked is False
    # A hair above the excess ⇒ blocked.
    v2 = _ev(STOCK_UP10, BENCH_UP5, "BUY", min_excess="5.0001")
    assert v2.blocked is True


def test_sell_min_excess_boundary_passes_on_equality() -> None:
    # Mirror of the LONG boundary on the SELL side (definition uses ≤ −min_excess).
    # STOCK_UP2 vs BENCH_UP5 ⇒ excess = −3; SELL passes when excess ≤ −min_excess.
    v = _ev(STOCK_UP2, BENCH_UP5, "SELL", min_excess="3")
    assert v.excess_pct == D(-3)
    assert v.blocked is False  # −3 ≤ −3
    v2 = _ev(STOCK_UP2, BENCH_UP5, "SELL", min_excess="3.0001")
    assert v2.blocked is True  # −3 > −3.0001 ⇒ fails the threshold


def test_missing_benchmark_fails_open() -> None:
    v = _ev(STOCK_UP10, None, "BUY")
    assert v.has_benchmark is False
    assert v.blocked is False
    assert v.excess_pct is None
    assert v.reasons == []


def test_short_series_fails_open() -> None:
    v = _ev(STOCK_UP10[:2], BENCH_UP5, "BUY")  # only 2 bars, need 4
    assert v.blocked is False
    assert v.has_benchmark is True
    assert v.reasons == ["series shorter than lookback + 1"]


def test_degenerate_base_price_fails_open() -> None:
    v = _ev([D(0), D(1), D(2), D(3)], BENCH_UP5, "BUY")  # stock_then == 0
    assert v.blocked is False
    assert v.reasons == ["degenerate base price"]


def test_degenerate_benchmark_base_price_fails_open() -> None:
    v = _ev(STOCK_UP10, [D(0), D(1), D(2), D(3)], "BUY")  # bench_then == 0
    assert v.blocked is False
    assert v.reasons == ["degenerate base price"]


def test_series_with_gap_fails_open() -> None:
    # A real feed can carry a hole; a None endpoint must fail OPEN, not raise
    # (never suppress on uncertainty). cast: we deliberately pass a malformed series.
    gapped = cast("list[Decimal]", [D(100), D(101), D(105), None])
    v = rs.evaluate(
        stock_closes=gapped,
        benchmark_closes=BENCH_UP5,
        side="BUY",
        lookback=3,
        min_excess_pct=D(0),
    )
    assert v.blocked is False
    assert v.reasons and "gap" in v.reasons[0]


def test_as_payload_is_json_safe_decimals_as_strings() -> None:
    v = _ev(STOCK_UP10, BENCH_UP5, "BUY")
    p = v.as_payload()
    assert p["excess_pct"] == "5.0000"
    assert p["stock_ret_pct"] == "10.0000"
    assert p["benchmark_label"] == "NIFTY50"
    assert p["side"] == "LONG"
    assert p["blocked"] is False
    assert isinstance(p["reasons"], list)


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_order_block_reason_never_blocks_off_or_shadow(mode: str) -> None:
    v = _ev(STOCK_UP2, BENCH_UP5, "BUY")  # blocked verdict
    assert v.blocked is True
    assert rs.order_block_reason(v, mode) is None  # only active blocks


def test_order_block_reason_active_blocks_ineligible() -> None:
    v = _ev(STOCK_UP2, BENCH_UP5, "BUY")
    reason = rs.order_block_reason(v, "active")
    assert reason is not None
    assert "relative-strength overlay" in reason


def test_order_block_reason_active_allows_eligible() -> None:
    v = _ev(STOCK_UP10, BENCH_UP5, "BUY")
    assert v.blocked is False
    assert rs.order_block_reason(v, "active") is None
