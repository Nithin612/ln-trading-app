"""A21 — marks are priced by the same model as fills.

Since 6.8.2 our *fills* paid the real half-spread while our *marks* used the untouched
last trade: the same system charging the spread on the way in and out, then valuing the
book as if it could be exited at a price nobody was offering. With 82% of live NSE books
wider than the flat 2 bps and ~29 open positions, reported unrealized P&L was
systematically optimistic by roughly a half-spread per position.

These tests pin the direction (long → bid, short → ask), the fallback, and — most
importantly — that a mark is never BETTER than the raw last trade, which is the property
that was violated.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.broker.depth import Depth
from app.broker.paper_broker import exit_mark, exit_side_for, simulate_fill
from app.core.config import settings

_WIDE = Depth(bid=Decimal("99.00"), ask=Decimal("101.00"), bid_qty=500, ask_qty=500)
_TIGHT = Depth(bid=Decimal("99.99"), ask=Decimal("100.01"), bid_qty=5000, ask_qty=5000)


@pytest.fixture
def haircut(monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest` zeroes `paper_slippage_bps` for the suite, so the flat path is a no-op
    unless a test asks for the haircut. Without this the flat-model assertions below would
    pass vacuously — which is exactly the kind of test this project keeps getting bitten
    by."""
    monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)


class TestExitSide:
    @pytest.mark.parametrize("side", ["LONG", "long"])
    def test_a_long_exits_by_selling(self, side: str) -> None:
        assert exit_side_for(side) == "SELL"

    @pytest.mark.parametrize("side", ["SHORT", "short"])
    def test_a_short_exits_by_buying(self, side: str) -> None:
        assert exit_side_for(side) == "BUY"

    @pytest.mark.parametrize("side", ["BUY", "SELL", "", "flat"])
    def test_an_order_side_is_refused_not_guessed(self, side: str) -> None:
        """`compute_pnl` and `roundtrip_charges` treat anything that is not LONG as a
        SHORT, so accepting `"BUY"` here would mark the position DOWN and then value it
        with the SHORT formula — turning the haircut into a phantom GAIN. The earlier
        version mapped BUY→SELL and this test pinned it as intended contract."""
        with pytest.raises(ValueError, match="POSITION side"):
            exit_side_for(side)


class TestMarkDirection:
    """The whole point: a mark must be what you could GET, not what last printed."""

    def test_a_long_is_marked_down_toward_the_bid(self) -> None:
        m = exit_mark(Decimal("100"), "LONG", depth=_WIDE, quantity=10)
        assert m.fill < Decimal("100")

    def test_a_short_is_marked_up_toward_the_ask(self) -> None:
        m = exit_mark(Decimal("100"), "SHORT", depth=_WIDE, quantity=10)
        assert m.fill > Decimal("100")

    @pytest.mark.parametrize("side", ["LONG", "SHORT"])
    @pytest.mark.parametrize("depth", [None, _WIDE, _TIGHT])
    @pytest.mark.parametrize(
        "ref",
        [
            Decimal("39"), Decimal("100"), Decimal("2500"),
            # OFF-GRID — where the bug actually lived. `ROUND_HALF_UP` to the nearest
            # tick carried the price back PAST the reference: 4.9% of 20,000 real 1m
            # closes marked a long ABOVE its last trade, and 27.2% of our closes are off
            # the ₹0.05 grid. The original parametrize used only grid-aligned prices and
            # could not fail (quant-verifier).
            Decimal("39.04"), Decimal("99.999"), Decimal("2500.03"), Decimal("1234.5678"),
        ],
    )
    @pytest.mark.usefixtures("haircut")
    def test_a_mark_is_never_better_than_the_last_trade(
        self, side: str, depth: Depth | None, ref: Decimal
    ) -> None:
        """The invariant that was violated, stated exactly.

        ⚠ It is "never BETTER", not "strictly worse" — TICK ROUNDING. A haircut smaller
        than half a tick rounds back to the reference, so the mark legitimately equals it
        (see `test_the_flat_mark_is_a_no_op_on_cheap_stocks`). Asserting strict movement
        here would be asserting an intention the code does not have."""
        m = exit_mark(ref, side, depth=depth, quantity=10)
        if side == "LONG":
            assert m.fill <= ref, "a long marked ABOVE the last trade"
        else:
            assert m.fill >= ref, "a short marked BELOW the last trade"

    @pytest.mark.parametrize("side", ["LONG", "SHORT"])
    def test_a_material_spread_strictly_moves_the_mark(self, side: str) -> None:
        """The other half: where the haircut clears half a tick it MUST bite, or the
        invariant above would be satisfied by doing nothing at all."""
        ref = Decimal("2500")
        m = exit_mark(ref, side, depth=_WIDE, quantity=10)
        assert m.fill != ref
        assert (m.fill < ref) if side == "LONG" else (m.fill > ref)

    @pytest.mark.usefixtures("haircut")
    def test_the_flat_mark_bites_even_on_cheap_stocks(self) -> None:
        """This USED to be `test_the_flat_mark_is_a_no_op_on_cheap_stocks`: with
        `ROUND_HALF_UP` a 2bps haircut on a ₹39 stock (₹0.0078) was smaller than half a
        ₹0.05 tick and rounded away entirely, so the historical mark did not move at all.
        Directional rounding removed that limitation — the fix for the off-grid bug turned
        out to fix this too, because a floor always reaches the next tick down."""
        for ref in (Decimal("39"), Decimal("100"), Decimal("2500")):
            assert exit_mark(ref, "LONG", depth=None, quantity=10).fill < ref

    def test_a_wider_book_marks_a_long_lower_than_a_tight_one(self) -> None:
        wide = exit_mark(Decimal("100"), "LONG", depth=_WIDE, quantity=10).fill
        tight = exit_mark(Decimal("100"), "LONG", depth=_TIGHT, quantity=10).fill
        assert wide < tight

    def test_size_impact_is_charged_on_the_exit_too(self) -> None:
        """A 5,000-share position cannot be exited at the touch either, so the mark must
        depend on quantity — not just on the spread."""
        small = exit_mark(Decimal("100"), "LONG", depth=_WIDE, quantity=1).fill
        large = exit_mark(Decimal("100"), "LONG", depth=_WIDE, quantity=5000).fill
        assert large < small


class TestItIsTheSameModelAsFills:
    """A21's actual requirement is not "haircut the mark" — it is that marks and fills
    cannot drift apart again. Pin the equivalence rather than the arithmetic."""

    @pytest.mark.parametrize(
        ("position_side", "order_side"), [("LONG", "SELL"), ("SHORT", "BUY")]
    )
    @pytest.mark.parametrize("depth", [None, _WIDE])
    @pytest.mark.usefixtures("haircut")
    def test_a_mark_equals_the_fill_of_the_closing_order(
        self, position_side: str, order_side: str, depth: Depth | None
    ) -> None:
        """⚠ `usefixtures("haircut")` is load-bearing: with conftest's
        `paper_slippage_bps=0` the two `depth=None` cells both returned the untouched
        reference, so an INVERTED `exit_side_for` still passed them (quant-verifier
        proved it by mutation). A test that survives the bug it guards is not a test."""
        ref = Decimal("250.75")
        mark = exit_mark(ref, position_side, depth=depth, quantity=100)
        fill = simulate_fill(ref, order_side, depth=depth, quantity=100)
        assert mark.fill == fill.fill
        assert mark.model == fill.model
        assert mark.slippage_bps == fill.slippage_bps

    @pytest.mark.usefixtures("haircut")
    def test_no_book_falls_back_to_the_flat_floor_exactly_as_a_fill_does(self) -> None:
        m = exit_mark(Decimal("100"), "LONG", depth=None, quantity=10)
        assert m.model == "flat"
        # NOT `slippage_bps == baseline_bps` — the flat branch assigns both from the same
        # local, so that comparison is a tautology (quant-verifier). Assert the VALUE.
        assert m.slippage_bps == Decimal("2.0")
        assert m.fill == exit_mark(Decimal("100"), "LONG", depth=None, quantity=99999).fill

    def test_a_live_book_is_used_when_present(self) -> None:
        m = exit_mark(Decimal("100"), "LONG", depth=_WIDE, quantity=10)
        assert m.model == "spread"
        # The wide book (2.00 spread on a 100 mid = 200bps, half = 100bps) must charge
        # far more than the 2bps floor, or the fixture is not exercising the spread path.
        assert m.slippage_bps > m.baseline_bps
