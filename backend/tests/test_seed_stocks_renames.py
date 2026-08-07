"""ISIN-keyed symbol-rename planning for the stock-master reseed.

Regression cover for a seed script that had silently stopped being re-runnable:
NSE renames a ticker, the equity CSV brings the NEW symbol carrying the OLD
row's ISIN, and the upsert — which conflicts on (symbol, exchange), not ISIN —
dies on `uq_stocks_isin` and rolls the whole reseed back. Six real renames were
sitting in the dev DB when this was found (AMIRCHAND → AEROPLANE,
GUJGASLTD → GUJENERGY, MIRCELECTR → ONIDA, VISASTEEL → VISACHROME,
ASHIKA → ASHIKAG, LYPSAGEMS → AURUS).

The identity rule under test: a rename is the SAME company, so the row is
renamed in place and keeps its id — and therefore its OHLCV history. A new row
would strand years of bars under a dead ticker.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from seed_stocks import plan_renames  # noqa: E402


def _equity(**pairs: str | None) -> dict[str, dict]:
    """{symbol: {isin}} shaped like fetch_equity_universe's output."""
    return {sym: {"isin": isin} for sym, isin in pairs.items()}


class TestPlanRenames:
    def test_renames_when_isin_moved_to_a_new_symbol(self) -> None:
        """The real AMIRCHAND → AEROPLANE case."""
        renames, collisions = plan_renames(
            equity=_equity(AEROPLANE="INE05TO01019"),
            all_syms={"AEROPLANE"},
            existing_by_isin={"INE05TO01019": (882, "AMIRCHAND")},
            existing_symbols={"AMIRCHAND"},
        )
        assert collisions == []
        assert renames == [("INE05TO01019", "AMIRCHAND", "AEROPLANE", 882)]

    def test_rename_targets_the_existing_row_id(self) -> None:
        """The id is what keeps the OHLCV history attached — assert it exactly."""
        renames, _ = plan_renames(
            equity=_equity(GUJENERGY="INE844O01030"),
            all_syms={"GUJENERGY"},
            existing_by_isin={"INE844O01030": (1234, "GUJGASLTD")},
            existing_symbols={"GUJGASLTD"},
        )
        assert renames[0][3] == 1234

    def test_unchanged_symbol_is_not_a_rename(self) -> None:
        renames, collisions = plan_renames(
            equity=_equity(RELIANCE="INE002A01018"),
            all_syms={"RELIANCE"},
            existing_by_isin={"INE002A01018": (1, "RELIANCE")},
            existing_symbols={"RELIANCE"},
        )
        assert renames == []
        assert collisions == []

    def test_brand_new_isin_is_not_a_rename(self) -> None:
        """A genuinely new listing must fall through to the normal insert."""
        renames, collisions = plan_renames(
            equity=_equity(NEWCO="INE999Z01011"),
            all_syms={"NEWCO"},
            existing_by_isin={},
            existing_symbols=set(),
        )
        assert renames == []
        assert collisions == []

    def test_symbol_without_an_isin_is_skipped(self) -> None:
        """F&O-only and index-only symbols carry no ISIN; they must not rename."""
        renames, collisions = plan_renames(
            equity={"NOISIN": {"isin": None}},
            all_syms={"NOISIN"},
            existing_by_isin={"INE05TO01019": (882, "AMIRCHAND")},
            existing_symbols={"AMIRCHAND"},
        )
        assert renames == []
        assert collisions == []

    def test_both_tickers_alive_is_a_collision_not_a_rename(self) -> None:
        """Merging two rows with separate history is not a seed script's call.

        Canary: renaming here would collapse two live instruments into one and
        silently pick a winner.
        """
        renames, collisions = plan_renames(
            equity=_equity(NEWSYM="INE111A01011"),
            all_syms={"NEWSYM"},
            existing_by_isin={"INE111A01011": (10, "OLDSYM")},
            existing_symbols={"OLDSYM", "NEWSYM"},
        )
        assert renames == []
        assert collisions == [("INE111A01011", "OLDSYM", "NEWSYM")]

    def test_a_collision_never_renames_the_row(self) -> None:
        """The incoming row keeps existing; only its ISIN is withheld upstream."""
        _renames, collisions = plan_renames(
            equity=_equity(NEWSYM="INE111A01011"),
            all_syms={"NEWSYM"},
            existing_by_isin={"INE111A01011": (10, "OLDSYM")},
            existing_symbols={"OLDSYM", "NEWSYM"},
        )
        assert {c[2] for c in collisions} == {"NEWSYM"}

    def test_is_deterministic_when_two_symbols_claim_one_isin(self) -> None:
        """A reseed must not be row-order dependent — first by sort order wins."""
        equity = _equity(BBB="INE111A01011", AAA="INE111A01011")
        args = {
            "existing_by_isin": {"INE111A01011": (10, "OLDSYM")},
            "existing_symbols": {"OLDSYM"},
        }
        first, _ = plan_renames(equity=equity, all_syms={"AAA", "BBB"}, **args)  # type: ignore[arg-type]
        second, _ = plan_renames(equity=equity, all_syms={"BBB", "AAA"}, **args)  # type: ignore[arg-type]
        assert first == second
        assert first[0][2] == "AAA"

    def test_second_claimant_becomes_a_collision_not_a_second_rename(self) -> None:
        """Once AAA has taken the row, BBB must not rename it again."""
        renames, collisions = plan_renames(
            equity=_equity(AAA="INE111A01011", BBB="INE111A01011"),
            all_syms={"AAA", "BBB"},
            existing_by_isin={"INE111A01011": (10, "OLDSYM")},
            existing_symbols={"OLDSYM"},
        )
        assert len(renames) == 1
        assert [c[2] for c in collisions] == ["BBB"]

    @pytest.mark.parametrize(
        ("old", "new", "isin"),
        [
            ("AMIRCHAND", "AEROPLANE", "INE05TO01019"),
            ("ASHIKA", "ASHIKAG", "INE094B01013"),
            ("LYPSAGEMS", "AURUS", "INE142K01011"),
            ("GUJGASLTD", "GUJENERGY", "INE844O01030"),
            ("MIRCELECTR", "ONIDA", "INE831A01028"),
            ("VISASTEEL", "VISACHROME", "INE286H01012"),
        ],
    )
    def test_every_rename_found_in_the_live_universe(
        self, old: str, new: str, isin: str
    ) -> None:
        """The six real cases that were blocking the reseed, pinned."""
        renames, collisions = plan_renames(
            equity=_equity(**{new: isin}),
            all_syms={new},
            existing_by_isin={isin: (1, old)},
            existing_symbols={old},
        )
        assert collisions == []
        assert renames == [(isin, old, new, 1)]
