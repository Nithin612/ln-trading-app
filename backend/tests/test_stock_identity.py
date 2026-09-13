"""D0 — the stock-identity pin (2026-09-14).

Every `stocks.id` was reassigned during the 2026-09-07 emergency rebuild, which is
why `deactivate_dead_stocks.py`'s documented reversal SQL now names the wrong
companies (plan §20/2): July's `stock_id = 228` was QUINTEGRA, today's is BSE.

The pin lets a rebuild FROM SOURCE reproduce the same id → symbol mapping. These
tests cover the comparison logic, which is pure — and the first of them is the
negative control: **a verifier that cannot detect the failure it exists for is
decoration**, so the 09-07 scenario is planted explicitly.
"""

from __future__ import annotations

from app.services.stock_identity import PinnedStock, diff, parse, serialise


def _pin(stock_id: int, symbol: str, isin: str | None = None) -> PinnedStock:
    return PinnedStock(
        stock_id=stock_id, symbol=symbol, isin=isin, first_seen="2026-09-07"
    )


class TestConflictDetection:
    def test_the_2026_09_07_scenario_is_detected(self) -> None:
        """NEGATIVE CONTROL. Plant the exact failure: a symbol keeps its name and
        changes its id, so every id-keyed artifact silently re-points."""
        pinned = [_pin(228, "QUINTEGRA"), _pin(500, "BSE")]
        live = {"QUINTEGRA": 900, "BSE": 228}  # ids swapped by a rebuild

        d = diff(pinned, live)

        assert not d.ok
        assert ("QUINTEGRA", 228, 900) in d.conflicts
        assert ("BSE", 500, 228) in d.conflicts

    def test_a_matching_database_has_no_conflicts(self) -> None:
        pinned = [_pin(1, "AAA"), _pin(2, "BBB")]
        d = diff(pinned, {"AAA": 1, "BBB": 2})
        assert d.ok
        assert d.conflicts == []

    def test_one_moved_id_among_many_is_still_caught(self) -> None:
        """The realistic shape: a rebuild that mostly reproduces itself."""
        pinned = [_pin(i, f"SYM{i}") for i in range(1, 51)]
        live = {f"SYM{i}": i for i in range(1, 51)}
        live["SYM37"] = 9999

        d = diff(pinned, live)

        assert d.conflicts == [("SYM37", 37, 9999)]
        assert not d.ok


class TestChurnIsNotDrift:
    """Only a CONFLICT is a defect. Listings come and go — failing on that would
    make the check noisy enough to be ignored, which is how guards die."""

    def test_a_new_listing_is_added_not_a_failure(self) -> None:
        d = diff([_pin(1, "OLD")], {"OLD": 1, "NEWLY": 77})
        assert d.added == ["NEWLY"]
        assert d.ok

    def test_a_delisting_is_missing_not_a_failure(self) -> None:
        d = diff([_pin(1, "OLD"), _pin(2, "GONE")], {"OLD": 1})
        assert d.missing == ["GONE"]
        assert d.ok

    def test_churn_and_a_conflict_together_still_fail(self) -> None:
        d = diff([_pin(1, "KEEP"), _pin(2, "GONE")], {"KEEP": 99, "NEWLY": 3})
        assert d.missing == ["GONE"]
        assert d.added == ["NEWLY"]
        assert d.conflicts == [("KEEP", 1, 99)]
        assert not d.ok


class TestRoundTrip:
    def test_serialise_then_parse_is_lossless(self) -> None:
        rows = [
            _pin(10, "WITHISIN", "INE001A01036"),
            _pin(20, "NOISIN", None),
        ]
        assert parse(serialise(rows)) == sorted(rows, key=lambda r: r.symbol)

    def test_an_empty_isin_round_trips_as_none_not_empty_string(self) -> None:
        """845 rows carry no ISIN. A '' would compare unequal to None and make
        every re-export look like a change."""
        assert parse(serialise([_pin(1, "X", None)]))[0].isin is None

    def test_output_is_sorted_by_symbol(self) -> None:
        """A re-export must produce a reviewable diff, not a reshuffle."""
        text = serialise([_pin(3, "ZZZ"), _pin(1, "AAA"), _pin(2, "MMM")])
        symbols = [line.split(",")[1] for line in text.strip().splitlines()[1:]]
        assert symbols == ["AAA", "MMM", "ZZZ"]

    def test_the_header_is_written(self) -> None:
        assert serialise([_pin(1, "A")]).startswith("stock_id,symbol,isin,first_seen")


class TestTheRealPinFile:
    def test_the_committed_pin_parses_and_is_internally_consistent(self) -> None:
        """The artifact itself, not a fixture: ids unique, symbols unique, and no
        blank symbol — the three ways a pin could be silently useless."""
        from pathlib import Path

        pin = Path(__file__).resolve().parents[1] / "seed" / "stock_identity.csv"
        rows = parse(pin.read_text())

        assert len(rows) > 3000
        assert len({r.stock_id for r in rows}) == len(rows)
        assert len({r.symbol for r in rows}) == len(rows)
        assert all(r.symbol for r in rows)
