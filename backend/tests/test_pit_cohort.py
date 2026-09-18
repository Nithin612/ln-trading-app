"""Queue item 14 — tests for the point-in-time liquidity cohort.

⭐ Every test here is a CANARY for a defect that actually shipped, not a hypothetical:
`test_cohort_cannot_see_the_future` plants M62's exact failure (rank on late liquidity, apply
early) and `test_a_name_that_died_after_the_window_is_still_admitted` plants M83's (a name that
traded in the window but not today). Both pass trivially against the old `load_frames`; both fail
loudly against it. That is the point.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from app.services.pit_cohort import (
    LOOKBACK_DAYS,
    InsufficientHistoryError,
    PitViolationError,
    assert_strictly_prior,
    liquid_as_of,
    liquid_over,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

AS_OF = date(2024, 6, 3)


async def _bars(
    db: AsyncSession, sid: int, start: date, days: int, close: str, volume: int
) -> None:
    """`days` consecutive CALENDAR days of bars — the cohort ranks on traded value, and the
    session calendar is irrelevant to what is being tested here."""
    for i in range(days):
        ts = datetime.combine(start + timedelta(days=i), time(0), tzinfo=UTC)
        await db.execute(
            text(
                "INSERT INTO ohlcv_1d (time, stock_id, open, high, low, close, volume,"
                " is_complete) VALUES (:t, :sid, :c, :c, :c, :c, :v, true)"
            ),
            {"t": ts, "sid": sid, "c": Decimal(close), "v": volume},
        )


@pytest.mark.asyncio
async def test_cohort_cannot_see_the_future(db: AsyncSession) -> None:
    """⛔⛔ M62's exact defect, planted. A name that becomes the most-traded in the market
    AFTER the as-of date must not enter a cohort constructed at that date."""
    quiet = await make_stock(db, symbol="LATEBLOOM")
    steady = await make_stock(db, symbol="STEADYCO")
    # LATEBLOOM is tiny before as_of and enormous after it.
    #
    # ⚠ The post-as_of run must OUTNUMBER the pre-as_of one. Ranking is by MEDIAN traded value,
    # so a minority of huge future bars leaves the median untouched and the test passes even
    # against a look-ahead window — which is exactly how the first version of this test came out
    # green under a mutation that reintroduced M62. 200 > 170 is what makes the canary fire.
    await _bars(db, quiet.id, AS_OF - timedelta(days=LOOKBACK_DAYS), 170, "10", 100)
    await _bars(db, quiet.id, AS_OF, 200, "10", 100_000_000)
    await _bars(db, steady.id, AS_OF - timedelta(days=LOOKBACK_DAYS), 170, "100", 10_000)
    await db.flush()

    cohort = await liquid_as_of(db, AS_OF, n=1)

    assert cohort == [steady.id], "the cohort ranked on post-as-of liquidity — this is M62"
    assert quiet.id not in cohort


@pytest.mark.asyncio
async def test_a_name_that_died_after_the_window_is_still_admitted(
    db: AsyncSession,
) -> None:
    """⛔ M83's defect, planted. `load_frames` required >100 bars in the last 180 days from
    TODAY, so 615 of 2,107 names that traded in 2021-22 could never enter. A trailing window
    ending at `as_of` must admit a name that was liquid then and is gone now."""
    dead = await make_stock(db, symbol="DELISTED", is_active=False)
    await _bars(db, dead.id, AS_OF - timedelta(days=LOOKBACK_DAYS), 170, "500", 50_000)
    await db.flush()

    assert dead.id in await liquid_as_of(db, AS_OF)


@pytest.mark.asyncio
async def test_insufficient_history_raises_rather_than_returning_empty(
    db: AsyncSession,
) -> None:
    """An empty cohort yields an empty cross-section, whose correlation is NaN, which a study
    averages away in silence. The archive's 313-session COVID block has no prior window at all."""
    s = await make_stock(db, symbol="NEWCO")
    await _bars(db, s.id, AS_OF - timedelta(days=10), 10, "100", 10_000)
    await db.flush()

    with pytest.raises(InsufficientHistoryError):
        await liquid_as_of(db, AS_OF)


def test_assert_strictly_prior_refuses_same_day_and_later() -> None:
    assert_strictly_prior(date(2023, 7, 2), date(2023, 7, 3))  # the only allowed shape
    with pytest.raises(PitViolationError):
        assert_strictly_prior(date(2023, 7, 3), date(2023, 7, 3))
    with pytest.raises(PitViolationError):
        assert_strictly_prior(date(2026, 9, 18), date(2023, 7, 3))  # M62, exactly


def test_the_lookback_is_not_a_caller_parameter() -> None:
    """⭐ Claude Q31: before M62 the 180-day lookback was invisible because there was only one.
    Exposing it as a keyword would hand item 5 a tunable nobody pre-registered."""
    import inspect

    params = inspect.signature(liquid_as_of).parameters
    assert "lookback" not in params
    assert "lookback_days" not in params
    assert set(params) == {"db", "as_of", "n"}


@pytest.mark.asyncio
async def test_liquid_over_never_returns_a_cohort_that_saw_its_own_session(
    db: AsyncSession,
) -> None:
    """The dynamic estimand's invariant, asserted rather than documented — documenting it is
    what failed for four rounds."""
    a = await make_stock(db, symbol="AAA")
    b = await make_stock(db, symbol="BBB")
    await _bars(db, a.id, AS_OF - timedelta(days=LOOKBACK_DAYS), 240, "100", 10_000)
    # BBB only starts trading heavily inside the measured span.
    await _bars(db, b.id, AS_OF, 60, "100", 99_000_000)
    await db.flush()

    sessions = [AS_OF, AS_OF + timedelta(days=1), AS_OF + timedelta(days=2)]
    cohorts = await liquid_over(db, sessions, n=2)

    assert cohorts, "measured nothing — the canary"
    assert all(b.id not in c for c in cohorts.values()), (
        "a session's own (and later) volume leaked into the cohort that scores it"
    )
