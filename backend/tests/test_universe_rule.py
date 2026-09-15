"""D2′a — the universe as a named, versioned RULE (2026-09-14). SHADOW ONLY.

`is_active` is a mutable boolean with three writers and no owner, and every one of
the 3,392 `stocks` rows was minted during the 2026-09-07 emergency rebuild — so there
was never an "original" to restore. The universe is therefore DERIVED and recorded,
not written. Nothing here touches `is_active`; flipping the source of truth is D2′b.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.services.universe_materialiser import materialise, parse_eq_listed
from app.services.universe_rule import (
    REASON_NOT_EQ_LISTED,
    REASON_NOT_KITE_TRADABLE,
    REASON_OK,
    RULE_VERSION,
    UniverseInputs,
    evaluate,
    shadow_diff,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

DAY = date(2026, 9, 14)


def _inputs(eq: set[str], kite: set[str]) -> UniverseInputs:
    return UniverseInputs(eq_listed=frozenset(eq), kite_tradable=frozenset(kite))


class TestTheRule:
    def test_listed_and_tradable_is_eligible(self) -> None:
        assert evaluate("RELIANCE", _inputs({"RELIANCE"}, {"RELIANCE"})) == (
            True,
            REASON_OK,
        )

    def test_not_eq_listed_is_excluded(self) -> None:
        assert evaluate("QUINTEGRA", _inputs(set(), {"QUINTEGRA"})) == (
            False,
            REASON_NOT_EQ_LISTED,
        )

    def test_listed_but_not_tradable_is_excluded(self) -> None:
        assert evaluate("NOKITE", _inputs({"NOKITE"}, set())) == (
            False,
            REASON_NOT_KITE_TRADABLE,
        )

    def test_the_listing_reason_wins_when_both_fail(self) -> None:
        """Reasons are ordered most-fundamental first: a name NSE does not list as
        EQ is reported that way even if Kite happens to carry an instrument."""
        assert evaluate("GONE", _inputs(set(), set()))[1] == REASON_NOT_EQ_LISTED

    def test_the_rule_has_no_bar_count_term(self) -> None:
        """LOAD-BEARING. Bar coverage is a fact about OUR OWN data completeness, and
        a rule that reads its own completeness SHRINKS when ingestion breaks — which
        is 2026-09-07 rebuilt inside the mechanism meant to prevent it. A name with
        too little history is unscoreable today, never unlisted.

        Asserted structurally: the inputs carry no coverage field, so no future edit
        can add the term without changing this signature."""
        assert set(UniverseInputs.__dataclass_fields__) == {"eq_listed", "kite_tradable"}


class TestShadowDiff:
    def test_both_directions_are_reported_separately(self) -> None:
        """The 2026-09-07 damage ran BOTH ways — good names inactive AND bad names
        active — and a single 'changed' count hides half of it."""
        live = {"GOOD": False, "BAD": True, "FINE": True, "DORMANT": False}
        verdicts = {
            "GOOD": (True, REASON_OK),
            "BAD": (False, REASON_NOT_EQ_LISTED),
            "FINE": (True, REASON_OK),
            "DORMANT": (False, REASON_NOT_EQ_LISTED),
        }

        d = shadow_diff(live, verdicts)

        assert d.would_activate == ["GOOD"]
        assert d.would_deactivate == [("BAD", REASON_NOT_EQ_LISTED)]
        assert (d.agree_active, d.agree_inactive) == (1, 1)
        assert d.total_changed == 2

    def test_a_symbol_the_rule_did_not_judge_is_skipped(self) -> None:
        assert shadow_diff({"UNKNOWN": True}, {}).total_changed == 0

    def test_full_agreement_reports_no_change(self) -> None:
        d = shadow_diff({"A": True}, {"A": (True, REASON_OK)})
        assert d.total_changed == 0 and d.agree_active == 1


class TestParseEqListed:
    """REGRESSION. EQUITY_L ships its header as
    `SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING,…` — every column after the
    first carries a LEADING SPACE. The first version of this parser used
    `row["SERIES"]`, matched nothing, and reported EQ=0 without raising, which would
    have "measured" that the rule deactivates the entire universe.
    `seed_stocks._csv_rows` already strips keys and says so in a comment.
    """

    REAL_HEADER = (
        "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
        " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    )

    def test_the_real_leading_space_header_parses(self) -> None:
        text = self.REAL_HEADER + "RELIANCE,Reliance Ltd,EQ,01-JAN-2000,10,1,INE002A01018,10\n"
        assert parse_eq_listed(text) == frozenset({"RELIANCE"})

    def test_non_eq_series_are_excluded(self) -> None:
        text = (
            self.REAL_HEADER
            + "EQCO,Eq Ltd,EQ,01-JAN-2000,10,1,INE001A01011,10\n"
            + "BECO,Be Ltd,BE,01-JAN-2000,10,1,INE002A01012,10\n"
            + "BZCO,Bz Ltd,BZ,01-JAN-2000,10,1,INE003A01013,10\n"
        )
        assert parse_eq_listed(text) == frozenset({"EQCO"})

    def test_an_unrecognised_schema_raises_instead_of_returning_empty(self) -> None:
        """A parser that returns EMPTY on a schema it does not recognise is the same
        silent-partial failure as everything else in this rebuild."""
        with pytest.raises(ValueError, match="no SERIES column"):
            parse_eq_listed("COL_A,COL_B\nx,y\n")

    def test_a_header_with_no_rows_parses_to_empty_here(self) -> None:
        """⚠ **This test and the one directly above it were in tension, and A10 resolved
        it by splitting the question.** That one says a parser returning EMPTY on a schema
        it does not recognise is the silent-partial failure of this whole rebuild; this
        one said an empty body "is empty, not an error". Both are right, about different
        things.

        `parse_eq_listed` is a PURE function of its text, and a header with no data rows
        genuinely parses to no symbols — that is arithmetic, not a judgement. What is NOT
        true is that zero EQ names can describe NSE: the real file carries ~2,292. That
        judgement is about the SOURCE, so it now lives in `_assert_plausible_equity_l`,
        which `download_equity_l` runs before this function ever sees the bytes
        (`test_equity_l_fetch.py`). Keeping it out of here is also what lets every fixture
        in this file hold two or three symbols."""
        assert parse_eq_listed(self.REAL_HEADER) == frozenset()


class TestMaterialise:
    async def test_only_eligible_names_are_recorded(self, db: AsyncSession) -> None:
        keep = await make_stock(db, symbol="KEEPCO")
        await make_stock(db, symbol="DROPCO")
        await db.commit()

        n = await materialise(
            db, as_of=DAY, inputs=_inputs({"KEEPCO"}, {"KEEPCO", "DROPCO"})
        )

        assert n == 1
        rows = (
            await db.execute(
                text("SELECT stock_id, rule_version FROM universe_snapshot WHERE as_of = :d"),
                {"d": DAY},
            )
        ).fetchall()
        assert [tuple(r) for r in rows] == [(keep.id, RULE_VERSION)]

    async def test_rerunning_a_day_replaces_it(self, db: AsyncSession) -> None:
        """A re-run after a fixed input must not leave two contradictory answers for
        one date."""
        a = await make_stock(db, symbol="AAA")
        b = await make_stock(db, symbol="BBB")
        await db.commit()

        await materialise(db, as_of=DAY, inputs=_inputs({"AAA", "BBB"}, {"AAA", "BBB"}))
        await materialise(db, as_of=DAY, inputs=_inputs({"AAA"}, {"AAA"}))

        rows = (
            await db.execute(
                text("SELECT stock_id FROM universe_snapshot WHERE as_of = :d"), {"d": DAY}
            )
        ).fetchall()
        assert [r[0] for r in rows] == [a.id]
        assert b.id not in [r[0] for r in rows]

    async def test_two_dates_coexist(self, db: AsyncSession) -> None:
        """The point-in-time property: 'was X in the universe on D' must not be
        overwritten by tomorrow's answer."""
        s = await make_stock(db, symbol="TIMECO")
        await db.commit()
        await materialise(db, as_of=DAY, inputs=_inputs({"TIMECO"}, {"TIMECO"}))
        await materialise(db, as_of=date(2026, 9, 15), inputs=_inputs(set(), set()))

        rows = (
            await db.execute(
                text("SELECT as_of, count(*) FROM universe_snapshot GROUP BY 1 ORDER BY 1")
            )
        ).fetchall()
        assert [(r[0], r[1]) for r in rows] == [(DAY, 1)]
        assert s.id is not None
