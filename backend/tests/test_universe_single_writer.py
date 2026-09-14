"""D2′b — the universe rule owns `stocks.is_active`, and the database enforces it.

⛔ THE FAILURE THIS ENDS. `is_active` was a mutable boolean with THREE writers and no
owner: `_ensure_historical_stocks` (INSERT false), `seed_stocks` (INSERT true), and
`deactivate_dead_stocks` (the only UPDATE). On 2026-09-07 a recovery script wrote it
wrong and the system spent five days scanning 1,322 micro-caps while ignoring RELIANCE
and TCS — silently, because nothing asserted who was allowed to write it.

Now exactly one code path may change it, and a trigger refuses the rest.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.services.universe_materialiser import apply_to_stocks, materialise
from app.services.universe_rule import UniverseInputs
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

DAY = date(2026, 9, 14)


def _inputs(eq: set[str], kite: set[str]) -> UniverseInputs:
    return UniverseInputs(eq_listed=frozenset(eq), kite_tradable=frozenset(kite))


async def _active(db: AsyncSession, symbol: str) -> bool:
    return bool(
        (
            await db.execute(
                text("SELECT is_active FROM stocks WHERE symbol = :s"), {"s": symbol}
            )
        ).scalar_one()
    )


class TestTheTriggerRefusesEveryOtherWriter:
    async def test_a_direct_update_is_refused(self, db: AsyncSession) -> None:
        """The 2026-09-07 shape: a script reaches in and writes the flag."""
        await make_stock(db, symbol="GUARDED", is_active=True)
        await db.commit()

        with pytest.raises(DBAPIError, match="ONE writer|universe rule"):
            await db.execute(
                text("UPDATE stocks SET is_active = false WHERE symbol = 'GUARDED'")
            )
            await db.commit()
        await db.rollback()

        assert await _active(db, "GUARDED") is True

    async def test_an_orm_update_is_refused_too(self, db: AsyncSession) -> None:
        """Not just raw SQL — the ORM path a well-meaning service would take."""
        s = await make_stock(db, symbol="ORMGUARD", is_active=True)
        await db.commit()

        s.is_active = False
        with pytest.raises(DBAPIError):
            await db.commit()
        await db.rollback()

    async def test_an_insert_is_not_blocked(self, db: AsyncSession) -> None:
        """A row that does not exist cannot have been evaluated, so its creator must
        supply an initial value. Only CHANGING the flag is a universe decision."""
        s = await make_stock(db, symbol="NEWBORN", is_active=False)
        await db.commit()
        assert s.id is not None
        assert await _active(db, "NEWBORN") is False

    async def test_updating_other_columns_still_works(self, db: AsyncSession) -> None:
        """The guard must not turn `stocks` into a read-only table — seed_stocks
        updates company_name, sector, lot_size and the index flags on every run."""
        await make_stock(db, symbol="OTHERCOL", is_active=True)
        await db.commit()

        await db.execute(
            text("UPDATE stocks SET company_name = 'Renamed Ltd' WHERE symbol = 'OTHERCOL'")
        )
        await db.commit()

        name = (
            await db.execute(
                text("SELECT company_name FROM stocks WHERE symbol = 'OTHERCOL'")
            )
        ).scalar_one()
        assert name == "Renamed Ltd"

    async def test_a_no_op_write_of_the_same_value_is_allowed(
        self, db: AsyncSession
    ) -> None:
        """`IS DISTINCT FROM` — an UPDATE that happens to touch the column without
        changing it is not a universe decision and must not fail."""
        await make_stock(db, symbol="NOOP", is_active=True)
        await db.commit()
        await db.execute(
            text("UPDATE stocks SET is_active = true WHERE symbol = 'NOOP'")
        )
        await db.commit()
        assert await _active(db, "NOOP") is True

    async def test_the_escape_hatch_works_and_is_named_in_the_error(
        self, db: AsyncSession
    ) -> None:
        """A guard nobody can bypass in an emergency gets DROPPED in an emergency, so
        the override is deliberate — and the exception has to teach it."""
        await make_stock(db, symbol="ESCAPE", is_active=True)
        await db.commit()

        try:
            await db.execute(
                text("UPDATE stocks SET is_active = false WHERE symbol = 'ESCAPE'")
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            assert "app.universe_writer" in str(exc)

        await db.execute(text("SET LOCAL app.universe_writer = 'on'"))
        await db.execute(
            text("UPDATE stocks SET is_active = false WHERE symbol = 'ESCAPE'")
        )
        await db.commit()
        assert await _active(db, "ESCAPE") is False

    async def test_the_override_does_not_leak_to_the_next_transaction(
        self, db: AsyncSession
    ) -> None:
        """`SET LOCAL`, not `SET`: the permission must die with the transaction, or a
        later statement on a pooled connection inherits the right to write."""
        await make_stock(db, symbol="LEAKY", is_active=True)
        await db.commit()

        await db.execute(text("SET LOCAL app.universe_writer = 'on'"))
        await db.execute(
            text("UPDATE stocks SET is_active = false WHERE symbol = 'LEAKY'")
        )
        await db.commit()  # transaction ends → permission ends

        with pytest.raises(DBAPIError):
            await db.execute(
                text("UPDATE stocks SET is_active = true WHERE symbol = 'LEAKY'")
            )
            await db.commit()
        await db.rollback()


class TestApplyToStocks:
    async def test_it_adopts_the_recorded_verdict_in_both_directions(
        self, db: AsyncSession
    ) -> None:
        """The D2′b flip in miniature: a good name switched on, a junk one off."""
        await make_stock(db, symbol="SHOULDBEON", is_active=False)
        await make_stock(db, symbol="SHOULDBEOFF", is_active=True)
        await db.commit()

        await materialise(
            db, as_of=DAY, inputs=_inputs({"SHOULDBEON"}, {"SHOULDBEON", "SHOULDBEOFF"})
        )
        activated, deactivated = await apply_to_stocks(db, as_of=DAY)

        assert (activated, deactivated) == (1, 1)
        assert await _active(db, "SHOULDBEON") is True
        assert await _active(db, "SHOULDBEOFF") is False

    async def test_it_is_idempotent(self, db: AsyncSession) -> None:
        """A nightly job must not report work it did not do."""
        await make_stock(db, symbol="STEADY", is_active=False)
        await db.commit()
        await materialise(db, as_of=DAY, inputs=_inputs({"STEADY"}, {"STEADY"}))

        first = await apply_to_stocks(db, as_of=DAY)
        second = await apply_to_stocks(db, as_of=DAY)

        assert first == (1, 0)
        assert second == (0, 0)

    async def test_it_refuses_a_date_with_no_snapshot(self, db: AsyncSession) -> None:
        """Otherwise 'no snapshot' would read as 'nothing is in the universe' and
        deactivate everything — the same accident as an empty instruments dump."""
        await make_stock(db, symbol="SURVIVOR", is_active=True)
        await db.commit()

        with pytest.raises(ValueError, match="no universe_snapshot"):
            await apply_to_stocks(db, as_of=date(2001, 1, 1))

        assert await _active(db, "SURVIVOR") is True

    async def test_it_can_write_where_everything_else_is_refused(
        self, db: AsyncSession
    ) -> None:
        """The point of the whole change: one writer, and it is this one."""
        await make_stock(db, symbol="ONLYPATH", is_active=False)
        await db.commit()
        await materialise(db, as_of=DAY, inputs=_inputs({"ONLYPATH"}, {"ONLYPATH"}))

        assert await apply_to_stocks(db, as_of=DAY) == (1, 0)
        assert await _active(db, "ONLYPATH") is True


class TestTheCollapseRail:
    """⛔ `apply_to_stocks` runs unattended on a beat, from a rule whose input is a CSV
    fetched over the internet. A truncated or reshaped feed yields a small `eq_listed`
    set — and without this rail the nightly job would quietly switch off most of the
    market. That is exactly what the `EQ=0` header bug of 2026-09-14 would have done
    had it reached this path instead of a `--diff`.
    """

    async def test_a_collapsed_snapshot_is_refused(self, db: AsyncSession) -> None:
        for i in range(10):
            await make_stock(db, symbol=f"BULK{i}", is_active=True)
        await db.commit()

        # a "feed" that found only one name
        await materialise(db, as_of=DAY, inputs=_inputs({"BULK0"}, {"BULK0"}))

        with pytest.raises(ValueError, match="COLLAPSE refused"):
            await apply_to_stocks(db, as_of=DAY)

        assert await _active(db, "BULK5") is True  # nothing switched off

    async def test_growth_is_never_refused(self, db: AsyncSession) -> None:
        """The D2′b flip itself doubled the universe — the rail must not block the
        repair it exists alongside."""
        for i in range(10):
            await make_stock(db, symbol=f"GROW{i}", is_active=False)
        await make_stock(db, symbol="GROWON", is_active=True)
        await db.commit()

        syms = {f"GROW{i}" for i in range(10)} | {"GROWON"}
        await materialise(db, as_of=DAY, inputs=_inputs(syms, syms))
        activated, deactivated = await apply_to_stocks(db, as_of=DAY)

        assert (activated, deactivated) == (10, 0)

    async def test_an_explicit_override_gets_through(self, db: AsyncSession) -> None:
        """A deliberate shrink must remain possible — a rail nobody can lower is a
        rail that gets deleted."""
        for i in range(10):
            await make_stock(db, symbol=f"SHRINK{i}", is_active=True)
        await db.commit()
        await materialise(db, as_of=DAY, inputs=_inputs({"SHRINK0"}, {"SHRINK0"}))

        activated, deactivated = await apply_to_stocks(db, as_of=DAY, min_fraction=0)

        assert (activated, deactivated) == (0, 9)
