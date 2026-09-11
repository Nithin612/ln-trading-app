"""B3 — the dated tick schedule, and the money-path bug it replaces.

`paper_tick_size` was one global ₹0.05 and the market has had two grids since June 2024.
On a ₹39 share the wrong grid charges ~10 bps of round-trip rounding the market does not
levy — ≈0.051R at a 2% stop, about 40% of the real 25.5 bps charge stack, and concentrated
on exactly the cheap tight-stop cohort.
"""

from datetime import date
from decimal import Decimal

import pytest
from app.broker import tick_schedule as ts
from app.broker.paper_broker import _round_tick, _tick_for
from app.core.config import Settings, settings

BEFORE = date(2024, 5, 1)
AFTER = date(2024, 7, 1)


class TestSchedule:
    def test_cheap_names_tick_at_one_paisa_after_the_change(self) -> None:
        assert ts.tick_for(Decimal("39"), as_of=AFTER) == Decimal("0.01")
        assert ts.tick_for(Decimal("20"), as_of=AFTER) == Decimal("0.01")
        assert ts.tick_for(Decimal("224.99"), as_of=AFTER) == Decimal("0.01")

    def test_expensive_names_never_moved(self) -> None:
        for day in (BEFORE, AFTER):
            assert ts.tick_for(Decimal("2500"), as_of=day) == Decimal("0.05")
            assert ts.tick_for(Decimal("300"), as_of=day) == Decimal("0.05")

    def test_before_the_change_everything_is_five_paise(self) -> None:
        """⭐ The date axis is load-bearing: a 2019 fill must not price on the 2026 grid."""
        assert ts.tick_for(Decimal("39"), as_of=BEFORE) == Decimal("0.05")
        assert ts.tick_for(Decimal("39"), as_of=date(2019, 10, 1)) == Decimal("0.05")
        assert ts.tick_for(Decimal("39"), as_of=date(2024, 5, 31)) == Decimal("0.05")
        assert ts.tick_for(Decimal("39"), as_of=date(2024, 6, 1)) == Decimal("0.01")

    def test_the_boundary_is_225_not_250(self) -> None:
        """⚠ Measured: ₹225–₹300 is a MIXED zone (39%/67%/84% on ₹0.05), because the tick
        is a property of the instrument set at a review, not of the instantaneous price.

        Taking the LOW end means we may over-charge a name that is really on ₹0.01, and can
        never under-charge one that is really on ₹0.05 — which is the module's contract.
        A ₹250 cut would hand out better-than-reality fills across a third of that zone.
        """
        assert ts.CHEAP_BAND_CEILING == Decimal("225")
        assert ts.tick_for(Decimal("224.99"), as_of=AFTER) == Decimal("0.01")
        assert ts.tick_for(Decimal("225"), as_of=AFTER) == Decimal("0.05")
        assert ts.tick_for(Decimal("249"), as_of=AFTER) == Decimal("0.05")

    def test_every_row_carries_a_source(self) -> None:
        """W5: a value with an external owner is not allowed into code without its source."""
        assert ts.SCHEDULE
        for band in ts.SCHEDULE:
            assert band.source.strip()
            assert band.tick > 0

    def test_rows_are_newest_first(self) -> None:
        dates = [b.valid_from for b in ts.SCHEDULE]
        assert dates == sorted(dates, reverse=True)

    def test_an_uncovered_price_fails_to_the_coarsest_grid(self) -> None:
        """A tick model that returns "no rounding" hands out fills better than reality."""
        assert ts.tick_for(Decimal("0"), as_of=date(1800, 1, 1)) == Decimal("0.05")


class TestBrokerWiring:
    def test_default_setting_uses_the_schedule(self) -> None:
        """⭐ The regression canary: a build that left the 0.05 default would fail here."""
        assert Settings().paper_tick_size == 0.0

    def test_positive_setting_overrides_the_schedule(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_tick_size", 0.05)
        assert _tick_for(Decimal("39"), as_of=AFTER) == Decimal("0.05")
        monkeypatch.setattr(settings, "paper_tick_size", 0.0)
        assert _tick_for(Decimal("39"), as_of=AFTER) == Decimal("0.01")

    @pytest.mark.parametrize(
        ("price", "side", "expected"),
        [
            # ₹39 archetype, post-change: ₹0.01 grid, still ADVERSE
            (Decimal("39.007"), "BUY", Decimal("39.0100")),
            (Decimal("39.007"), "SELL", Decimal("39.0000")),
            # ₹2,500: unchanged ₹0.05 grid, still adverse
            (Decimal("2500.07"), "BUY", Decimal("2500.1000")),
            (Decimal("2500.07"), "SELL", Decimal("2500.0500")),
        ],
    )
    def test_acceptance_criterion(
        self, price: Decimal, side: str, expected: Decimal,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⭐ BUILD_QUEUE B3: a ₹39 name rounds on ₹0.01, a ₹2,500 name on ₹0.05, and the
        adverse contract (BUY ceils, SELL floors) survives both."""
        monkeypatch.setattr(settings, "paper_tick_size", 0.0)
        assert _round_tick(price, side) == expected

    def test_the_overcharge_the_bug_caused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⭐ The finding, in money: the old grid costs ~10 bps more per round trip on ₹39.

        Worst-case adverse rounding is one full tick on each leg when the raw price sits
        just past a grid point. ₹0.05 → ₹0.10/share round trip on ₹39 = 25.6 bps;
        ₹0.01 → ₹0.02 = 5.1 bps. The EXCESS is the artifact, and it is the cohort the
        research corpus is full of.
        """
        raw_buy, raw_sell = Decimal("39.001"), Decimal("38.999")
        monkeypatch.setattr(settings, "paper_tick_size", 0.05)  # the bug
        old = _round_tick(raw_buy, "BUY") - _round_tick(raw_sell, "SELL")
        monkeypatch.setattr(settings, "paper_tick_size", 0.0)  # the schedule
        new = _round_tick(raw_buy, "BUY") - _round_tick(raw_sell, "SELL")
        assert old == Decimal("0.1000")
        assert new == Decimal("0.0200")
        excess_bps = (old - new) / Decimal("39") * Decimal("10000")
        assert Decimal("20") < excess_bps < Decimal("21")

    def test_an_expensive_name_is_unaffected_by_the_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The canary for the other side: B3 must not move any ≥₹225 fill."""
        raw = Decimal("502.5733")
        monkeypatch.setattr(settings, "paper_tick_size", 0.05)
        before = _round_tick(raw, "BUY")
        monkeypatch.setattr(settings, "paper_tick_size", 0.0)
        assert _round_tick(raw, "BUY") == before == Decimal("502.6000")
