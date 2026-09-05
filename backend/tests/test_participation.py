"""A37 + T3 — the volume-participation impact, and its parametrised fill tests.

Our 6.8.2 model charged the real half-spread plus a size-vs-TOP-OF-BOOK impact. Neither
notices that an order is large relative to the stock's DAILY VOLUME: the notional cap
bounds a position in rupees, not in liquidity. **SRTL is the named case** — a ₹39
micro-cap, 2,666 shares; a ₹1 lakh position in a name trading ₹5 lakh a day is a fifth of
a session and is not fillable at the quoted price, yet we modelled it as free.

T3's shape is `(participation, expected_fill)` — given a market-impact model, assert the
resulting fill. That is what `TestParticipationCurve` is.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.broker.depth import Depth
from app.broker.paper_broker import exit_mark, participation_bps, simulate_fill
from app.core.config import settings
from app.services.liquidity import median_traded_value

#: ₹5 lakh a day — the SRTL shape.
_THIN_ADV = Decimal("500000")
#: ₹100 crore a day — a liquid large-cap.
_DEEP_ADV = Decimal("1000000000")
_BOOK = Depth(bid=Decimal("38.95"), ask=Decimal("39.05"), bid_qty=5000, ask_qty=5000)


@pytest.fixture(autouse=True)
def _knobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest` zeroes `paper_slippage_bps`, which would let a flat-path assertion pass
    for the wrong reason. Pin every knob this module depends on."""
    monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
    monkeypatch.setattr(settings, "paper_participation_enabled", True)
    monkeypatch.setattr(settings, "paper_participation_k", 0.1)


class TestParticipationCurve:
    """T3: given a participation fraction, assert the impact. Values are `k × p² × 10⁴`
    with k = 0.1, the zipline `VolumeShareSlippage` calibration."""

    @pytest.mark.parametrize(
        ("participation", "expected_bps"),
        [
            (Decimal("0.001"), Decimal("0.001")),   # 0.1% — negligible
            (Decimal("0.025"), Decimal("0.625")),   # zipline's 2.5% bar cap
            (Decimal("0.05"), Decimal("2.5")),
            (Decimal("0.10"), Decimal("10")),
            (Decimal("0.20"), Decimal("40")),       # the SRTL neighbourhood
            (Decimal("0.50"), Decimal("250")),
            (Decimal("1.00"), Decimal("1000")),     # a whole day's volume
        ],
    )
    def test_impact_matches_the_quadratic_model(
        self, participation: Decimal, expected_bps: Decimal
    ) -> None:
        adv = Decimal("1000000")
        bps, got = participation_bps(adv * participation, adv)
        assert got == participation
        assert bps == pytest.approx(expected_bps, rel=Decimal("1e-9"))

    def test_impact_grows_faster_than_linearly(self) -> None:
        """The whole point of quadratic: doubling your size must more than double the
        cost, or a large order is just a lot of small ones."""
        adv = Decimal("1000000")
        single, _ = participation_bps(Decimal("50000"), adv)   # 5%
        double, _ = participation_bps(Decimal("100000"), adv)  # 10%
        assert double > single * 2


class TestFailsOpen:
    """Unknown liquidity must never read as infinitely illiquid."""

    @pytest.mark.parametrize("adv", [None, Decimal("0"), Decimal("-1")])
    def test_missing_or_unusable_adv_charges_nothing(self, adv: Decimal | None) -> None:
        bps, part = participation_bps(Decimal("100000"), adv)
        assert bps == Decimal(0)
        assert part == Decimal(0)

    def test_a_zero_size_order_charges_nothing(self) -> None:
        assert participation_bps(Decimal("0"), _THIN_ADV) == (Decimal(0), Decimal(0))

    def test_the_knob_switches_it_off_entirely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "paper_participation_enabled", False)
        assert participation_bps(Decimal("100000"), _THIN_ADV) == (Decimal(0), Decimal(0))


class TestItReachesTheFill:
    """The impact is worthless if it does not change a price."""

    def test_the_srtl_order_is_no_longer_modelled_as_free(self) -> None:
        """2,666 shares of a ₹39 stock = ₹103,974 against ₹5 lakh a day ≈ 20.8%."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        assert f.participation > Decimal("0.20")
        assert f.participation_bps > Decimal("40")
        # Was 2 bps (the flat floor) before A37.
        assert f.slippage_bps > Decimal("40")
        assert f.fill > Decimal("39.15")

    def test_a_small_order_in_the_same_stock_is_untouched(self) -> None:
        """The model must bite on SIZE, not on the stock. 100 shares is 0.78% of the day."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=100, adv_value=_THIN_ADV
        )
        assert f.participation_bps < Decimal("0.1")

    def test_the_same_order_in_a_liquid_name_is_untouched(self) -> None:
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_DEEP_ADV
        )
        assert f.participation_bps < Decimal("0.01")

    def test_it_applies_on_the_spread_path_too(self) -> None:
        with_adv = simulate_fill(
            Decimal("39"), "BUY", depth=_BOOK, quantity=2666, adv_value=_THIN_ADV
        )
        without = simulate_fill(Decimal("39"), "BUY", depth=_BOOK, quantity=2666)
        assert with_adv.slippage_bps > without.slippage_bps

    def test_it_applies_on_the_flat_path_too(self) -> None:
        """A thin stock usually has NO live book, so charging participation only on the
        spread path would exempt exactly the names the model exists for."""
        with_adv = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        without = simulate_fill(Decimal("39"), "BUY", depth=None, quantity=2666)
        assert with_adv.model == "flat"
        assert with_adv.slippage_bps > without.slippage_bps

    def test_the_total_is_still_bounded_by_the_ceiling(self) -> None:
        """Participation overlaps the top-of-book term rather than being orthogonal to it,
        so an illiquid name trips both. The ceiling is what stops the sum running away."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=_BOOK, quantity=2_000_000, adv_value=_THIN_ADV
        )
        assert f.slippage_bps <= Decimal(str(settings.paper_slippage_max_bps))

    def test_the_verdict_is_stamped_for_the_audit_trail(self) -> None:
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        payload = f.as_payload()
        assert Decimal(payload["participation_bps"]) > Decimal("40")  # type: ignore[arg-type]
        assert Decimal(payload["participation_pct"]) > Decimal("20")  # type: ignore[arg-type]


class TestMarksPayItToo:
    """A31: charging participation on the FILL but not on the MARK would re-open exactly
    the optimism A21 closed. Getting out of a fifth of a day's volume costs what getting
    in cost."""

    def test_an_exit_mark_charges_participation(self) -> None:
        marked = exit_mark(Decimal("39"), "LONG", depth=None, quantity=2666, adv_value=_THIN_ADV)
        plain = exit_mark(Decimal("39"), "LONG", depth=None, quantity=2666)
        assert marked.participation_bps > Decimal("40")
        assert marked.fill < plain.fill  # a long marks further DOWN

    def test_a_short_mark_moves_the_other_way(self) -> None:
        marked = exit_mark(Decimal("39"), "SHORT", depth=None, quantity=2666, adv_value=_THIN_ADV)
        plain = exit_mark(Decimal("39"), "SHORT", depth=None, quantity=2666)
        assert marked.fill > plain.fill


class TestMedianHelper:
    def test_median_of_an_even_series_is_the_midpoint(self) -> None:
        assert median_traded_value(
            [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
        ) == Decimal("25")

    def test_median_of_an_odd_series(self) -> None:
        assert median_traded_value([Decimal("30"), Decimal("10"), Decimal("20")]) == Decimal("20")

    def test_empty_is_zero(self) -> None:
        assert median_traded_value([]) == Decimal("0")

    def test_it_is_a_median_not_a_mean(self) -> None:
        """One freak volume day must not make an illiquid stock look tradeable — the
        reason the liquidity gate uses a median, and why this shares its helper."""
        spiky = [Decimal("1000")] * 19 + [Decimal("100000000")]
        assert median_traded_value(spiky) == Decimal("1000")
