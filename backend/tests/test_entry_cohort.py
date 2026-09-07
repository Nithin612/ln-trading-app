"""Entry-cohort (vintage) attribution.

The assertions that matter are the ones stopping this view from lying:

- a cohort with picks still open is **provisional**, and its realised figure is not its
  result — merging realised and open into one number is the single way to make vintage
  attribution mislead;
- a cohort with nothing resolved has **no win rate**, not 0% — "no data" and "everything
  lost" must not render the same.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.trading import Position
from app.services import entry_cohort as ec
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

_DAY = datetime(2026, 9, 1, 4, 0, tzinfo=UTC)


async def _pos(
    db: AsyncSession,
    user_id: int,
    stock_id: int,
    *,
    opened: datetime,
    pnl: Decimal | None = None,
    unrealized: Decimal | None = None,
) -> Position:
    p = Position(
        user_id=user_id, stock_id=stock_id, mode="paper", side="LONG",
        quantity=10, avg_entry_price=Decimal("100"), current_sl=Decimal("95"),
        realized_pnl=pnl if pnl is not None else Decimal("0"),
        unrealized_pnl=unrealized,
        opened_at=opened,
        closed_at=opened + timedelta(hours=6) if pnl is not None else None,
    )
    db.add(p)
    await db.flush()
    return p


class TestGrouping:
    async def test_groups_by_entry_day_not_exit_day(self, db: AsyncSession) -> None:
        """⭐ The whole point. Two picks made the same day, closed days apart, belong to
        ONE cohort — under exit-date grouping they would land in two different reports."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        p1 = Position(
            user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
            avg_entry_price=Decimal("100"), realized_pnl=Decimal("100"),
            opened_at=_DAY, closed_at=_DAY + timedelta(days=1),
        )
        p2 = Position(
            user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=10,
            avg_entry_price=Decimal("100"), realized_pnl=Decimal("-40"),
            opened_at=_DAY, closed_at=_DAY + timedelta(days=6),
        )
        db.add_all([p1, p2])
        await db.commit()

        cohorts = await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1))
        assert len(cohorts) == 1, "same entry day ⇒ one cohort, whatever the exit dates"
        assert cohorts[0].picks == 2
        assert cohorts[0].realized == Decimal("60.00")

    async def test_same_day_entry_and_exit_needs_no_special_case(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, pnl=Decimal("25"))
        await db.commit()

        c = (await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1)))[0]
        assert c.picks == 1 and c.resolved == 1 and c.still_open == 0
        assert not c.in_flight

    async def test_separate_days_are_separate_cohorts(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, pnl=Decimal("10"))
        await _pos(db, user.id, stock.id, opened=_DAY + timedelta(days=1),
                   pnl=Decimal("-10"))
        await db.commit()

        cohorts = await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1))
        assert [c.picks for c in cohorts] == [1, 1]
        assert cohorts[0].entry_day < cohorts[1].entry_day, "oldest first"


class TestProvisionalVerdicts:
    async def test_open_picks_make_the_cohort_in_flight(self, db: AsyncSession) -> None:
        """⭐ The rule that stops this view lying.

        A cohort whose picks are still open has realised ₹0 — reporting that as 'flat'
        would be false about a cohort sitting deeply underwater on the mark.
        """
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, unrealized=Decimal("-4593"))
        await db.commit()

        c = (await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1)))[0]
        assert c.in_flight
        assert c.realized == Decimal("0.00")
        assert c.open_mtm == Decimal("-4593.00")

    async def test_realised_and_open_are_never_merged(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, pnl=Decimal("500"))
        await _pos(db, user.id, stock.id, opened=_DAY, unrealized=Decimal("-200"))
        await db.commit()

        c = (await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1)))[0]
        assert c.realized == Decimal("500.00")
        assert c.open_mtm == Decimal("-200.00")
        assert c.total_so_far == Decimal("300.00"), "available, but as a MIXED figure"
        assert c.in_flight, "and the cohort is still provisional"

    async def test_win_rate_is_none_not_zero_when_nothing_resolved(
        self, db: AsyncSession
    ) -> None:
        """'No data' and 'everything lost' must not render the same — the same
        undefined-vs-measured distinction `app/core/ratios.py` draws."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, unrealized=Decimal("-10"))
        await db.commit()

        c = (await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1)))[0]
        assert c.win_pct is None

    async def test_win_rate_counts_only_resolved(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(db, user.id, stock.id, opened=_DAY, pnl=Decimal("10"))
        await _pos(db, user.id, stock.id, opened=_DAY, pnl=Decimal("-10"))
        await _pos(db, user.id, stock.id, opened=_DAY, unrealized=Decimal("999"))
        await db.commit()

        c = (await ec.load_cohorts(db, since=_DAY.date() - timedelta(days=1)))[0]
        assert c.resolved == 2 and c.still_open == 1
        assert c.win_pct == 50.0, "the open winner must not inflate the rate"


class TestRendering:
    def test_in_flight_rows_are_flagged(self) -> None:
        c = ec.Cohort(
            entry_day=_DAY.date(), picks=5, resolved=2, still_open=3,
            realized=Decimal("100"), open_mtm=Decimal("-50"), wins=1,
        )
        out = "\n".join(ec.render_lines([c]))
        assert "⏳" in out
        assert "PROVISIONAL" in out.upper()

    def test_caption_warns_against_merging(self) -> None:
        """The table cannot stop a reader adding the two columns; the caption can."""
        c = ec.Cohort(
            entry_day=_DAY.date(), picks=1, resolved=1, still_open=0,
            realized=Decimal("10"), open_mtm=Decimal("0"), wins=1,
        )
        out = "\n".join(ec.render_lines([c]))
        assert "separate on purpose" in out

    def test_undefined_win_rate_renders_as_dash(self) -> None:
        c = ec.Cohort(
            entry_day=_DAY.date(), picks=3, resolved=0, still_open=3,
            realized=Decimal("0"), open_mtm=Decimal("-4593"), wins=0,
        )
        out = "\n".join(ec.render_lines([c]))
        assert "| — |" in out
        assert "0%" not in out.split("| — |")[0].split("\n")[-1]

    def test_says_so_when_nothing_has_resolved(self) -> None:
        c = ec.Cohort(
            entry_day=_DAY.date(), picks=5, resolved=0, still_open=5,
            realized=Decimal("0"), open_mtm=Decimal("-100"), wins=0,
        )
        out = "\n".join(ec.render_lines([c]))
        assert "none of them is a result" in out

    def test_best_and_worst_use_only_settled_cohorts(self) -> None:
        """⭐ An in-flight cohort must never be crowned best or worst — its number is not
        final, so the ranking would churn as marks moved.

        Needs TWO settled cohorts: with only one, best == worst and the block is
        suppressed anyway, which would let this pass without testing anything.
        """
        good = ec.Cohort(
            entry_day=_DAY.date(), picks=2, resolved=2, still_open=0,
            realized=Decimal("500"), open_mtm=Decimal("0"), wins=2,
        )
        bad = ec.Cohort(
            entry_day=_DAY.date() + timedelta(days=1), picks=2, resolved=2, still_open=0,
            realized=Decimal("-300"), open_mtm=Decimal("0"), wins=0,
        )
        # Extreme on BOTH sides, so it would win either superlative if eligible.
        flying = ec.Cohort(
            entry_day=_DAY.date() + timedelta(days=2), picks=2, resolved=1, still_open=1,
            realized=Decimal("9999"), open_mtm=Decimal("0"), wins=1,
        )
        out = "\n".join(ec.render_lines([good, bad, flying]))
        verdict = out.split("Best fully-resolved")[-1]
        assert "Best fully-resolved" in out, "two settled cohorts ⇒ the block must render"
        assert "9,999" not in verdict, "an in-flight cohort cannot be best or worst"
        assert "₹500" in verdict and "-300" in verdict

    def test_empty_input_renders_nothing(self) -> None:
        assert ec.render_lines([]) == []
