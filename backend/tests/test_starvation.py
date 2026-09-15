"""V6 / A5 — the built-and-STARVED alarm.

⭐ **One of the project's two recurring defect shapes.** `kite_instruments` empty before U1
(so the live worker subscribed to nothing), `categories` empty, `strategy_profiles` empty.
Each time the code was correct, wired and green — it simply had no data to act on, and
nothing anywhere said so.

⭐⭐ **The case that proves it is live.** `strategy_profiles` is seeded by migration
`o1p2q3r4s5t6_phase2_profile_seeds` and dev is at head, yet it holds **zero rows**: the
2026-09-07 rebuild restored the schema with alembic already marked applied, so the seed
never re-ran and cannot — `alembic upgrade` is a no-op on a revision it thinks is done.
Four production call sites read that table. **A migration that seeds reference data is
invisible to every check we own once it has been marked applied.**
"""
from __future__ import annotations

import pytest
from app.services.starvation import (
    CONSUMED_TABLES,
    ConsumedTable,
    Starvation,
    check_starvation,
    render_lines,
    to_notification,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _by(rows: list[Starvation], table: str) -> Starvation:
    return next(r for r in rows if r.entry.table == table)


class TestItFiresOnAnEmptyConsumedTable:
    async def test_an_empty_table_with_consumers_is_starved(
        self, db: AsyncSession
    ) -> None:
        """conftest truncates everything, so every declared table starts empty — which is
        the starved state by construction and exactly what the alarm must see."""
        rows = await check_starvation(db)
        assert _by(rows, "strategy_profiles").is_starved
        md = "\n".join(render_lines(rows))
        assert "STARVED TABLE" in md and "strategy_profiles" in md
        # The REMEDY travels with the alarm — "X is empty" alone moves the investigation
        # rather than starting it.
        assert "o1p2q3r4s5t6" in md
        # …and so do the consumers, which is what turns a row count into a consequence.
        assert "profiles/pipeline.py" in md

    async def test_a_populated_table_is_not_starved(self, db: AsyncSession) -> None:
        """The canary: without it, an alarm that fires on everything passes the test
        above. `stocks` is declared, so populating it must clear exactly that entry."""
        await make_stock(db, symbol="AAA")
        await db.commit()
        rows = await check_starvation(db)
        assert _by(rows, "stocks").rows == 1
        assert not _by(rows, "stocks").is_starved
        assert _by(rows, "strategy_profiles").is_starved  # still empty, still named

    async def test_the_notification_names_the_remedy_and_the_consumers(
        self, db: AsyncSession
    ) -> None:
        n = to_notification(await check_starvation(db))
        assert n is not None and n.event == "starved_table"
        body = n.render()
        assert "REMEDY" in body and "strategy_profiles" in body
        assert "quietly do nothing" in body  # the consequence, not just the fact

    async def test_nothing_is_said_when_every_table_is_populated(
        self, db: AsyncSession
    ) -> None:
        healthy = [Starvation(e, 5) for e in CONSUMED_TABLES]
        assert to_notification(healthy) is None
        md = "\n".join(render_lines(healthy))
        assert "STARVED TABLE" not in md and "Consumed tables populated" in md


class TestTheRegistryIsHonest:
    def test_every_entry_names_a_populator_and_a_consumer(self) -> None:
        """⚠ The rule that keeps this registry meaningful. A table with no consumer is
        not starved, it is UNUSED; a table with no populator is a design gap, not an
        alarm. Both were verified by hand before each entry was added, and this stops the
        next entry from skipping that."""
        for e in CONSUMED_TABLES:
            assert e.populated_by.strip(), f"{e.table} declares no populator"
            assert e.observed_by, f"{e.table} declares no consumer"
            assert all(c.strip() for c in e.observed_by)

    def test_alarms_that_already_own_a_table_are_not_duplicated(self) -> None:
        """⛔ `ohlcv_1d`/`fo_bhavcopy` belong to `feed_health`, `nse_holidays` to
        `calendar_health`, `universe_snapshot` to `universe_health`. Restating their
        emptiness here would be a second instrument for one fact, which is how a reader
        learns that two alarms mean one problem."""
        owned = {"ohlcv_1d", "fo_bhavcopy", "nse_holidays", "universe_snapshot",
                 "india_vix_daily"}
        assert {e.table for e in CONSUMED_TABLES} & owned == set()

    def test_user_created_tables_are_absent(self) -> None:
        """⚠ 21 of 57 tables are empty in dev and MOST are correctly so — nobody has made
        a watchlist or written a journal entry. Declaring those would train the reader to
        ignore the alarm within a week."""
        user_made = {"watchlists", "watchlist_items", "journal_entries", "saved_screens",
                     "manual_assets", "mf_holdings", "categories", "corporate_actions"}
        assert {e.table for e in CONSUMED_TABLES} & user_made == set()

    async def test_every_declared_table_actually_exists(self, db: AsyncSession) -> None:
        """A typo in a table name would make the probe fail, land in `not measurable`, and
        report nothing — a registry entry that can never fire."""
        for e in CONSUMED_TABLES:
            got = (
                await db.execute(
                    text("SELECT to_regclass(:t)"), {"t": f"public.{e.table}"}
                )
            ).scalar()
            assert got is not None, f"{e.table} does not exist"


class TestProbeNeverRaises:
    async def test_a_failing_count_degrades_to_unmeasurable_not_starved(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⚠ `rows is None` must NOT read as zero. "We could not count" and "there is
        nothing there" are different claims, and only one of them is an alarm."""
        bogus = (ConsumedTable("no_such_table_xyz", "nothing", ("nobody",)),)
        monkeypatch.setattr("app.services.starvation.CONSUMED_TABLES", bogus)
        rows = await check_starvation(db)  # must not raise
        assert rows[0].rows is None
        assert not rows[0].is_measurable
        assert not rows[0].is_starved  # unknown, never alarmed
        assert to_notification(rows) is None


class TestBeatTask:
    async def test_the_beat_pushes_and_names_the_starved_tables(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.tasks.health_tasks import _starvation_payload

        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _starvation_payload(db)
        assert result["status"] == "alert"
        assert "strategy_profiles" in result["starved"]  # type: ignore[operator]
        assert len(sent) == 1

    async def test_a_fed_system_reports_ok_and_pushes_nothing(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silent success — the A11 rule. Also the canary: an alarm that always fires
        would pass the test above."""
        from app.services.starvation import ConsumedTable
        from app.tasks.health_tasks import _starvation_payload

        await make_stock(db, symbol="AAA")
        await db.commit()
        monkeypatch.setattr(
            "app.services.starvation.CONSUMED_TABLES",
            (ConsumedTable("stocks", "seed_stocks.py", ("everything",)),),
        )
        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _starvation_payload(db)
        assert result == {"status": "ok", "starved": []}
        assert sent == []
