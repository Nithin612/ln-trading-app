"""The directional entry trigger (Bucket C #2, 2026-10-03), through the REAL tick engine.

The user-facing "entry" alert was the symmetric ±0.5% `zone`, so a BUY drifting DOWN into its
entry fired the same alert as a BUY breaking UP through it — an alert claiming a direction it
never checked. The zone stays (outcome recording reads it); the entry alert is now a
direction-aware cross at the entry price. A correctness fix to an alert, not a P&L claim.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import tradecore
from app.broker.live_levels import _signal_levels, entry_trigger_level_id, signal_level_ids
from app.broker.live_worker import TF_MINUTES, session_bounds_ist
from app.services.signal_outcomes import TOUCH_SOURCES

DAY = date(2026, 7, 9)
OPEN_TS, CLOSE_TS = session_bounds_ist(DAY)
SID = 42


def _sig(direction: str) -> dict[str, Any]:
    buy = direction == "BUY"
    return {"id": f"sig-{direction}", "entry": Decimal("100.00"), "direction": direction,
            "sl": Decimal("95.00") if buy else Decimal("105.00"),
            "tp": Decimal("110.00") if buy else Decimal("90.00"),
            "classification": "swing", "shadow": False}


def _fired(sig: dict[str, Any], prices: list[str]) -> list[tuple[str, str]]:
    """Feed ticks through the real engine; return (source, tag) of every trigger fired."""
    levels, meta = _signal_levels(sig)
    book = tradecore.LiveBook(OPEN_TS, CLOSE_TS, TF_MINUTES)
    book.ensure_instruments([SID])
    book.set_levels(SID, levels)
    out = []
    for k, p in enumerate(prices):
        for e in book.on_ticks([(SID, OPEN_TS + 5 + k, p, None, 10)]):
            if e["kind"] == "trigger":
                out.append((str(meta[e["id"]]["source"]), str(e["tag"])))
    return out


class TestTheLevels:
    def test_buy_gets_a_cross_up_trigger_at_entry_beside_the_unchanged_zone(self) -> None:
        levels, meta = _signal_levels(_sig("BUY"))
        trig = next(lv for lv in levels if lv["id"] == entry_trigger_level_id("sig-BUY"))
        assert (trig["kind"], trig["price"]) == ("cross_up", "100.0000")
        assert meta[trig["id"]]["source"] == "entry_trigger"
        zone = next(lv for lv in levels if lv["id"] == signal_level_ids("sig-BUY")[0])
        assert (zone["kind"], zone["low"], zone["high"]) == ("zone", "99.5000", "100.5000")

    def test_sell_mirrors_with_cross_down(self) -> None:
        levels, _ = _signal_levels(_sig("SELL"))
        trig = next(lv for lv in levels if lv["id"] == entry_trigger_level_id("sig-SELL"))
        assert trig["kind"] == "cross_down"

    def test_the_trigger_id_collides_with_no_other_slot(self) -> None:
        assert entry_trigger_level_id("sig-BUY") not in signal_level_ids("sig-BUY")

    def test_outcome_recording_does_not_read_the_trigger(self) -> None:
        """No recorded number moves: entry_touched_at still comes from the zone alone."""
        assert "entry_zone" in TOUCH_SOURCES and "entry_trigger" not in TOUCH_SOURCES


class TestThroughTheRealEngine:
    def test_a_buy_drifting_down_into_its_band_is_not_an_entry(self) -> None:
        """101 → 100.20 enters the band from ABOVE: the zone touch still fires (outcomes need
        it), the entry trigger does not. The view-level canary — this touch used to BE the entry
        alert — is the frontend's default-entry-only test; the next test fails on the old code
        (it had no trigger at all)."""
        fired = _fired(_sig("BUY"), ["101.00", "100.20"])
        assert ("entry_zone", "zone_enter") in fired
        assert not any(src == "entry_trigger" for src, _ in fired)

    def test_a_buy_rising_through_its_entry_is_an_entry(self) -> None:
        fired = _fired(_sig("BUY"), ["99.00", "100.10"])
        assert ("entry_trigger", "cross_up") in fired

    def test_a_sell_falling_through_its_entry_is_an_entry_and_rising_is_not(self) -> None:
        assert ("entry_trigger", "cross_down") in _fired(_sig("SELL"), ["101.00", "99.90"])
        assert not any(s == "entry_trigger" for s, _ in _fired(_sig("SELL"), ["99.00", "99.80"]))


class TestWhatCrossedMeans:
    """bug-hunter 2026-10-03 — each pinned through the real engine."""

    def test_chop_around_the_entry_fires_the_trigger_about_as_often_as_the_zone(self) -> None:
        """test_entry_trigger_rearms_every_10bp: ±0.15% chop fired the trigger 4× vs the zone 1×
        at the 10 bp level-cross band. At 50 bp it fires once."""
        chop = ["99.85", "100.05"] * 4
        fired = _fired(_sig("BUY"), chop)
        assert fired.count(("entry_trigger", "cross_up")) == 1
        assert fired.count(("entry_zone", "zone_enter")) == 1

    def test_a_full_pullback_beyond_the_band_rearms_it(self) -> None:
        fired = _fired(_sig("BUY"), ["99.00", "100.10", "99.40", "100.10"])
        assert fired.count(("entry_trigger", "cross_up")) == 2

    def test_an_open_at_the_entry_that_rises_is_not_an_entry(self) -> None:
        """Crossed ON OUR WATCH: the first tick only arms the side, so an open exactly at the
        entry (the prior close) and a rise never crossed it this session."""
        fired = _fired(_sig("BUY"), ["100.00", "100.50"])
        assert not any(src == "entry_trigger" for src, _ in fired)
        assert ("entry_zone", "zone_enter") in fired  # the record still sees the entry trade

    def test_the_exact_entry_tick_is_asymmetric(self) -> None:
        """price == level reads AboveOrAt: a BUY fires AT the entry, a SELL needs a tick below."""
        assert ("entry_trigger", "cross_up") in _fired(_sig("BUY"), ["99.95", "100.00"])
        assert not any(s == "entry_trigger" for s, _ in _fired(_sig("SELL"), ["100.05", "100.00"]))
        assert ("entry_trigger", "cross_down") in _fired(_sig("SELL"), ["100.05", "99.99"])
