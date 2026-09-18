"""Queue item 14 — the point-in-time liquidity cohort, as an INSTRUMENT that refuses.

## ⛔⛔ The defect this exists to make unrepeatable

`swing_dependence_probe.load_frames` ranks the top 250 names by median `close * volume` over
**`now() - interval '180 days'`** and every consumer applies that cohort to historical panels —
`e2_score_ic.py` (the programme's central null), `b7_hazard.py`, and the swing probe itself.
Measured 2026-09-18 (**M62**): a point-in-time cohort as of 2023-07-03 shares **164 of 250
(65.6%)** with the shipped one, so **34.4% of E2's cross-section was selected using liquidity
information from AFTER the measurement window**. As of 2021-01-01 the overlap falls to 54.0%.

⭐ A second defect sits in the same clause, and it is survivorship rather than look-ahead:
`HAVING count(*) > 100` over the **last** 180 days is a liveness test on TODAY. **615 of the 2,107
names that actually traded in 2021-22 (29.2%) cannot enter that cohort at all** (M83). Ranking on a
trailing window that ENDS at `as_of` fixes both — a name that was liquid before `as_of` and
delisted afterwards is admitted, exactly as it should be.

⭐⭐ **Why this is a function and not a rule in prose.** "Every cohort carries its construction
date" was adopted in round 7 and violated in the very next row of the same table (M52), then again
unnoticed inside `load_frames` for four more rounds. A prose rule that fails inside one document is
not a control. This module is the control.

## The estimand, pre-registered (round 11, ChatGPT 1.2)

A cohort fixed once at a study's start and a cohort rebuilt for every measurement date are
**different estimands**, and the question E2 asks — *does the score order forward returns among the
names eligible on that date* — is the **DYNAMIC** one. `liquid_over` is therefore the entry point a
study should call; `liquid_as_of` is its single-date primitive.

⚠ **`LOOKBACK_DAYS` is pinned at 180 and is deliberately NOT a parameter.** Before M62 the lookback
was invisible because there was only one; exposing it now would hand item 5 a tunable nobody
pre-registered (Claude Q31).

⚠ **The rebuild cadence is monthly, and that is COARSENESS, never look-ahead.** A per-session
rebuild over 1,727 sessions is 1,727 window aggregates; a monthly cohort is computed at the month's
first measured session and is therefore strictly prior to every date it is applied to. The failure
this module exists to prevent is using the future, and a monthly rebuild uses none of it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ⛔ Pinned, not parameters (see the docstring). The bar count is what makes this a LIQUIDITY
# cohort rather than a list of names that happened to print once in the window.
LOOKBACK_DAYS = 180
MIN_BARS_IN_WINDOW = 100
DEFAULT_N = 250

# Below this the trailing window is not a ranking window, it is a handful of sessions. The
# archive's COVID block (2019-10-01 -> 2020-12-31) has no prior window by construction, which is
# why queue item 11b seals it with "no liquid_as_of inside it".
MIN_SESSIONS_IN_WINDOW = 60


class PitViolationError(ValueError):
    """A cohort was constructed from data at or after the dates it is applied to."""


class InsufficientHistoryError(ValueError):
    """The trailing window holds too few sessions to rank on.

    ⚠ Raised rather than returning an empty list ON PURPOSE. An empty cohort silently produces an
    empty cross-section, whose correlation is NaN, which a study will happily average away.
    """


def assert_strictly_prior(as_of: date, applied_to: date) -> None:
    """Refuse a cohort whose construction date is not strictly before its earliest use.

    For a study that builds one cohort by hand instead of calling `liquid_over`. `as_of ==
    applied_to` is a violation too: the ranking window must close BEFORE the first measured
    session, or the cohort has seen the session it is about to score.
    """
    if as_of >= applied_to:
        raise PitViolationError(
            f"cohort as-of {as_of} is not strictly before the earliest measurement date "
            f"{applied_to} — it would rank on data the study is about to measure. This is M62: "
            f"load_frames ranked on now()-{LOOKBACK_DAYS}d and applied it to 2023-07-03 panels."
        )


async def liquid_as_of(db: AsyncSession, as_of: date, *, n: int = DEFAULT_N) -> list[int]:
    """Top-`n` `stock_id`s by median daily traded value over the 180 days **before** `as_of`.

    The window is `[as_of - LOOKBACK_DAYS, as_of)` — half-open, so a bar printed ON `as_of` can
    never influence the cohort that scores `as_of`.

    Raises `InsufficientHistoryError` when the window holds fewer than
    `MIN_SESSIONS_IN_WINDOW` sessions.
    """
    start = as_of - timedelta(days=LOOKBACK_DAYS)

    sessions = (
        await db.execute(
            text(
                "SELECT count(DISTINCT time::date) FROM ohlcv_1d "
                "WHERE time >= :start AND time < :as_of"
            ),
            {"start": start, "as_of": as_of},
        )
    ).scalar_one()
    if sessions < MIN_SESSIONS_IN_WINDOW:
        raise InsufficientHistoryError(
            f"{sessions} sessions in [{start}, {as_of}) — need {MIN_SESSIONS_IN_WINDOW}. "
            f"There is no prior ranking window here."
        )

    rows = (
        await db.execute(
            text(
                """SELECT stock_id FROM ohlcv_1d
                   WHERE time >= :start AND time < :as_of
                   GROUP BY stock_id HAVING count(*) >= :min_bars
                   ORDER BY percentile_cont(0.5)
                            WITHIN GROUP (ORDER BY close * volume) DESC
                   LIMIT :n"""
            ),
            {"start": start, "as_of": as_of, "min_bars": MIN_BARS_IN_WINDOW, "n": n},
        )
    ).all()
    return [r[0] for r in rows]


async def liquid_over(
    db: AsyncSession, sessions: Iterable[date], *, n: int = DEFAULT_N
) -> dict[date, list[int]]:
    """⭐ THE DYNAMIC ESTIMAND — one cohort per measurement date, each strictly prior to it.

    Rebuilt at the first measured session of each calendar month and carried forward within it
    (see the docstring on cadence). The strictly-prior invariant is ASSERTED on each rebuild
    rather than documented, because documenting it is what failed last time.

    Sessions whose window has no prior history are **omitted**, not silently given an empty
    cohort — the caller sees a shorter dict and can compare `len()` with what it passed in.
    """
    out: dict[date, list[int]] = {}
    cache: dict[tuple[int, int], list[int]] = {}
    for session in sorted(sessions):
        key = (session.year, session.month)
        if key not in cache:
            try:
                cohort = await liquid_as_of(db, session, n=n)
            except InsufficientHistoryError:
                continue
            cache[key] = cohort
            # The window closed strictly before this session; asserted so a future cadence
            # change cannot quietly break the invariant this module exists for.
            assert_strictly_prior(session - timedelta(days=1), session)
        out[session] = cache[key]
    return out
