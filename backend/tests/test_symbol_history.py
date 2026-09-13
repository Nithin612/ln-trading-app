"""D1′ — identity churn is recorded, and an identity anchor is never silently
rewritten (2026-09-14).

TWO KINDS OF CHURN, one handled-but-invisible and one not handled at all:

  RENAME — ISIN keeps, symbol changes. `seed_stocks.plan_renames` applies these in
  place so the row keeps its id, and with it every bar, signal and position. Correct,
  and it left NO TRACE: "what was this id called in July?" was unanswerable, which is
  half of why §20/2's reversal SQL resolves to the wrong companies.

  REUSE — symbol keeps, ISIN changes (NSE re-issuing a delisted ticker). This fell
  through to `isin = COALESCE(EXCLUDED.isin, stocks.isin)`, which OVERWROTE the anchor
  and merged two companies into one row — the new company inheriting the dead one's id
  and its entire price history.

⚠ REUSE frequency is unmeasurable retrospectively: the merge overwrites its own
evidence. Hence record-and-refuse rather than restructure.
"""

from __future__ import annotations

from datetime import date

from app.services import symbol_history as sh
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

DAY = date(2026, 9, 14)
LATER = date(2026, 10, 1)


async def _intervals(db: AsyncSession, stock_id: int) -> list[tuple]:
    rows = (
        await db.execute(
            text(
                "SELECT symbol, isin, valid_from, valid_to, reason FROM symbol_history"
                " WHERE stock_id = :sid ORDER BY valid_from, id"
            ),
            {"sid": stock_id},
        )
    ).fetchall()
    return [tuple(r) for r in rows]


class TestClassifyIsinChange:
    """Pure, and the distinction the whole module turns on."""

    def test_same_isin_is_unchanged(self) -> None:
        assert sh.classify_isin_change("INE001A01036", "INE001A01036") == "unchanged"

    def test_no_incoming_isin_is_unchanged(self) -> None:
        """The feed having nothing to say must never erase what we know."""
        assert sh.classify_isin_change("INE001A01036", None) == "unchanged"

    def test_filling_an_empty_anchor_is_safe(self) -> None:
        assert sh.classify_isin_change(None, "INE001A01036") == "fill"

    def test_a_different_isin_on_a_known_symbol_is_reuse(self) -> None:
        """The company-merge case. Never resolved automatically — a reuse and a
        data correction look identical in the feed."""
        assert sh.classify_isin_change("INE001A01036", "INE999Z01011") == "reuse"


class TestSeedingAndIntervals:
    async def test_seed_opens_one_interval_per_stock(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="HISTCO", isin="INE001A01036")
        await db.commit()

        assert await sh.seed_from_stocks(db, on=DAY) == 1
        await db.commit()

        rows = await _intervals(db, s.id)
        assert len(rows) == 1
        assert rows[0][0] == "HISTCO"
        assert rows[0][3] is None  # open
        assert rows[0][4] == sh.REASON_SEED

    async def test_seeding_twice_adds_nothing(self, db: AsyncSession) -> None:
        """A seed script runs daily; it must not grow a row per run."""
        s = await make_stock(db, symbol="IDEMPCO")
        await db.commit()
        await sh.seed_from_stocks(db, on=DAY)
        await db.commit()

        assert await sh.seed_from_stocks(db, on=LATER) == 0
        await db.commit()
        assert len(await _intervals(db, s.id)) == 1

    async def test_opening_an_interval_closes_the_previous_one(
        self, db: AsyncSession
    ) -> None:
        """The invariant: exactly ONE open interval per stock. It lives in the
        writer because a partial unique index cannot express 'one NULL per group'
        while the closed intervals share the same columns."""
        s = await make_stock(db, symbol="FIRST", isin="INE001A01036")
        await db.commit()
        await sh.open_interval(
            db, stock_id=s.id, symbol="FIRST", exchange="NSE",
            isin="INE001A01036", on=DAY, reason=sh.REASON_SEED,
        )
        await sh.open_interval(
            db, stock_id=s.id, symbol="SECOND", exchange="NSE",
            isin="INE001A01036", on=LATER, reason=sh.REASON_RENAME,
        )
        await db.commit()

        rows = await _intervals(db, s.id)
        assert [r[0] for r in rows] == ["FIRST", "SECOND"]
        assert rows[0][3] == LATER  # closed on the day the next one opened
        assert rows[1][3] is None
        assert sum(1 for r in rows if r[3] is None) == 1


class TestRenameIsNowVisible:
    async def test_a_rename_records_both_sides_and_keeps_the_id(
        self, db: AsyncSession
    ) -> None:
        """The AMIRCHAND → AEROPLANE shape. The row keeps its id (and its bars);
        what changes is that the old ticker is now recoverable."""
        s = await make_stock(db, symbol="AMIRCHAND", isin="INE05TO01019")
        await db.commit()
        await sh.seed_from_stocks(db, on=DAY)
        await db.commit()

        s.symbol = "AEROPLANE"
        await db.flush()
        await sh.record_rename(
            db, stock_id=s.id, new_symbol="AEROPLANE", exchange="NSE",
            isin="INE05TO01019", on=LATER,
        )
        await db.commit()

        rows = await _intervals(db, s.id)
        assert [r[0] for r in rows] == ["AMIRCHAND", "AEROPLANE"]
        assert rows[0][3] == LATER and rows[1][3] is None
        assert rows[1][4] == sh.REASON_RENAME
        # "What was this id called before 2026-10-01?" — answerable now.
        assert rows[0][0] == "AMIRCHAND"


class TestReuseDetection:
    async def test_a_differing_isin_on_a_known_symbol_is_reported(
        self, db: AsyncSession
    ) -> None:
        await make_stock(db, symbol="REUSED", isin="INE001A01036")
        await db.commit()

        conflicts = await sh.detect_isin_conflicts(db, {"REUSED": "INE999Z01011"})

        assert conflicts == [("REUSED", "INE001A01036", "INE999Z01011")]

    async def test_a_matching_isin_is_not_reported(self, db: AsyncSession) -> None:
        await make_stock(db, symbol="SAMECO", isin="INE001A01036")
        await db.commit()
        assert await sh.detect_isin_conflicts(db, {"SAMECO": "INE001A01036"}) == []

    async def test_a_row_with_no_stored_isin_is_not_a_conflict(
        self, db: AsyncSession
    ) -> None:
        """Filling an empty anchor is safe and must not be reported as a merge."""
        await make_stock(db, symbol="NOISIN", isin=None)
        await db.commit()
        assert await sh.detect_isin_conflicts(db, {"NOISIN": "INE001A01036"}) == []

    async def test_an_empty_feed_is_cheap_and_silent(self, db: AsyncSession) -> None:
        assert await sh.detect_isin_conflicts(db, {}) == []


class TestTheAnchorIsFilledOnceNeverRewritten:
    """The behaviour change in `seed_stocks`' upsert, asserted directly in SQL so it
    cannot drift from the script: `COALESCE(stocks.isin, EXCLUDED.isin)`, not the
    reverse. Overwriting is how one company inherits another's history."""

    async def test_an_existing_anchor_survives_a_conflicting_write(
        self, db: AsyncSession
    ) -> None:
        s = await make_stock(db, symbol="ANCHORCO", isin="INE001A01036")
        await db.commit()

        await db.execute(
            text(
                "INSERT INTO stocks (symbol, exchange, isin, company_name, lot_size,"
                " tick_size, is_fno, is_nifty50, is_banknifty, is_finnifty, is_active)"
                " VALUES ('ANCHORCO','NSE','INE999Z01011','Other Co',1,0.05,"
                " false,false,false,false,true)"
                " ON CONFLICT (symbol, exchange) DO UPDATE SET"
                "   isin = COALESCE(stocks.isin, EXCLUDED.isin)"
            )
        )
        await db.commit()
        await db.refresh(s)

        assert s.isin == "INE001A01036"  # old code: INE999Z01011

    async def test_an_empty_anchor_is_still_filled(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="EMPTYCO", isin=None)
        await db.commit()

        await db.execute(
            text(
                "INSERT INTO stocks (symbol, exchange, isin, company_name, lot_size,"
                " tick_size, is_fno, is_nifty50, is_banknifty, is_finnifty, is_active)"
                " VALUES ('EMPTYCO','NSE','INE777Y01010','Empty Co',1,0.05,"
                " false,false,false,false,true)"
                " ON CONFLICT (symbol, exchange) DO UPDATE SET"
                "   isin = COALESCE(stocks.isin, EXCLUDED.isin)"
            )
        )
        await db.commit()
        await db.refresh(s)

        assert s.isin == "INE777Y01010"
