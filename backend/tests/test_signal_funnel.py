"""V1 — the candidate funnel (2026-09-14).

⭐ An empty state has NO STOCK IN CONTEXT, so asking it to name a per-stock cause is a
category error — which is why "nothing meets the confluence gate right now" could never be
fixed by better copy. What it can honestly do is state the SCOPE that was searched.

⭐⭐ And the reason this ranked P0 is not the copy: `priced_today` against `breadth_median`
is a COVERAGE detector, and the 6.8.6 feed alarm asserts RECENCY — so this would have seen
the 2026-09-07 collapse that alarm read green through.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.market_data import OhlcvDaily
from app.services.funnel import Funnel, load_funnel
from app.services.signal_service import MIN_CANDLES_TO_SCORE
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

TODAY = datetime.now(tz=UTC).replace(hour=10, minute=0, second=0, microsecond=0)


async def _bar(db: AsyncSession, stock_id: int, when: datetime) -> None:
    db.add(
        OhlcvDaily(
            time=when, stock_id=stock_id, open=Decimal("100"), high=Decimal("101"),
            low=Decimal("99"), close=Decimal("100"), volume=1000, is_complete=True,
        )
    )


async def _bars(db: AsyncSession, stock_id: int, *, sessions: int) -> None:
    """`sessions` daily bars ending on TODAY — the newest one lands on the latest session
    so the name counts as priced, while the depth decides whether it is admitted."""
    for i in range(sessions):
        await _bar(db, stock_id, TODAY - timedelta(days=i))
    await db.commit()


class TestTheFunnelIsNested:
    async def test_each_stage_is_a_subset_of_the_one_above(
        self, db: AsyncSession
    ) -> None:
        """⚠ THE DESIGN CONSTRAINT. Raw "names with a bar" is LARGER than the universe
        (D3 ingests every known NSE symbol regardless of tradeability — measured 2,637
        bars against 2,291 in universe). Rendering that as a stage would show a funnel
        WIDENING, which reads as a bug. The bar stage is therefore scoped to the
        universe."""
        live = await make_stock(db, symbol="FUNLIVE", is_active=True)
        dormant = await make_stock(db, symbol="FUNDEAD", is_active=False)
        await _bar(db, live.id, TODAY)
        await _bar(db, dormant.id, TODAY)  # has a bar but is NOT in the universe
        await db.commit()

        f = await load_funnel(db)

        assert f.known >= f.in_universe >= f.priced_today >= f.signals_live
        assert f.in_universe == 1
        assert f.priced_today == 1, "the out-of-universe bar must not inflate the stage"

    async def test_a_universe_name_without_a_bar_narrows_the_stage(
        self, db: AsyncSession
    ) -> None:
        a = await make_stock(db, symbol="HASBAR", is_active=True)
        await make_stock(db, symbol="NOBAR", is_active=True)
        await _bar(db, a.id, TODAY)
        await db.commit()

        f = await load_funnel(db)

        assert f.in_universe == 2
        assert f.priced_today == 1


class TestBreadthDetection:
    async def test_a_collapse_shows_as_a_shortfall(self, db: AsyncSession) -> None:
        """⭐ THE POINT. Ten names price normally for several sessions, then only two
        price today — the 2026-09-07 shape. The funnel makes that visible; a recency
        alarm cannot see it."""
        stocks = [await make_stock(db, symbol=f"BR{i}", is_active=True) for i in range(10)]
        for back in range(1, 6):
            when = TODAY - timedelta(days=back)
            for s in stocks:
                await _bar(db, s.id, when)
        for s in stocks[:2]:  # today: only 2 of 10
            await _bar(db, s.id, TODAY)
        await db.commit()

        f = await load_funnel(db)

        assert f.priced_today == 2
        assert f.breadth_median == 10
        assert f.breadth_shortfall_pct == 80.0

    async def test_a_healthy_day_shows_no_shortfall(self, db: AsyncSession) -> None:
        stocks = [await make_stock(db, symbol=f"OK{i}", is_active=True) for i in range(5)]
        for back in range(0, 5):
            when = TODAY - timedelta(days=back)
            for s in stocks:
                await _bar(db, s.id, when)
        await db.commit()

        f = await load_funnel(db)

        assert f.priced_today == 5
        assert f.breadth_shortfall_pct == 0.0

    def test_shortfall_is_none_when_there_is_no_reference(self) -> None:
        """A24 — a count with nothing to compare against is not judgeable, and saying so
        beats printing a number that reads as fine."""
        f = Funnel(known=10, in_universe=5, priced_today=5, admitted_to_scoring=5,
                   signals_live=0, session=None, breadth_median=None)
        assert f.breadth_shortfall_pct is None


class TestTheMissingRungIsDeclared:
    async def test_assessed_is_reported_as_unavailable_not_zero(
        self, db: AsyncSession
    ) -> None:
        """⛔ Nothing persists how many panels the scorer evaluated. A silent missing
        rung invites the reader to assume ZERO, which is worse than four honest stages —
        so the absence is stated rather than implied."""
        await make_stock(db, symbol="RUNG", is_active=True)
        await db.commit()

        f = await load_funnel(db)

        assert f.assessed_available is False

    async def test_an_empty_database_does_not_explode(self, db: AsyncSession) -> None:
        f = await load_funnel(db)
        assert f.known == 0 and f.priced_today == 0
        assert f.session is None
        assert f.breadth_shortfall_pct is None


class TestTheSessionTravelsWithTheCount:
    async def test_the_session_is_reported(self, db: AsyncSession) -> None:
        """A24 — "2,286 priced" is meaningless without which session it refers to."""
        s = await make_stock(db, symbol="SESS", is_active=True)
        await _bar(db, s.id, TODAY)
        await db.commit()

        f = await load_funnel(db)

        assert f.session == TODAY.date()


class TestTheAdmissionRung:
    """⭐⭐ ROUND 5 — the rung that makes the other four honest.

    `signal_service` refuses a name with fewer than `MIN_CANDLES_TO_SCORE` completed daily
    candles BEFORE scoring. Without this stage the whole drop from `priced_today` to
    `signals_live` is forced onto the confluence gate — it is the only mechanism a reader
    has left to explain it — so "the engine looked at everything and liked none" renders
    identically to "the engine never looked at 8% of them".
    """

    async def test_a_short_history_name_is_priced_but_not_admitted(
        self, db: AsyncSession
    ) -> None:
        deep = await make_stock(db, symbol="DEEPHIST", is_active=True)
        thin = await make_stock(db, symbol="THINHIST", is_active=True)
        await db.commit()

        # Both print a bar on the latest session; only one carries enough history.
        await _bars(db, deep.id, sessions=MIN_CANDLES_TO_SCORE + 5)
        await _bars(db, thin.id, sessions=MIN_CANDLES_TO_SCORE - 5)

        f = await load_funnel(db)
        assert f.priced_today == 2, "both printed today"
        assert f.admitted_to_scoring == 1, "only the deep-history name can be scored"

    async def test_the_rung_is_nested_between_priced_and_signals(
        self, db: AsyncSession
    ) -> None:
        """A funnel that widens is a bug that looks like data — pinned in both directions."""
        for i in range(4):
            st = await make_stock(db, symbol=f"NEST{i}", is_active=True)
            await db.commit()
            await _bars(db, st.id, sessions=MIN_CANDLES_TO_SCORE + i)

        f = await load_funnel(db)
        assert f.known >= f.in_universe >= f.priced_today >= f.admitted_to_scoring
        assert f.admitted_to_scoring >= f.signals_live

    async def test_the_threshold_is_the_scan_s_own_and_not_a_copy(self) -> None:
        """⭐ W5. A hardcoded 50 in the funnel would drift from the gate it describes, and
        the drift would be silent: the funnel would keep reporting a stage boundary the
        scan no longer uses. Asserted by identity, not by value."""
        from app.services import funnel as funnel_mod
        from app.services import signal_service

        assert funnel_mod.MIN_CANDLES_TO_SCORE is signal_service.MIN_CANDLES_TO_SCORE

    async def test_assessed_still_reports_unavailable(self, db: AsyncSession) -> None:
        """⛔ The admission stage being computable does NOT make the scorer's own panel
        count known. The residual drop stays unattributable and must keep saying so."""
        f = await load_funnel(db)
        assert f.assessed_available is False
