"""V1 — the candidate funnel: what the scan actually looked at.

⭐ **Why this replaces "no opportunities" copy.** An empty state has **no stock in
context**, so asking it to name a per-stock cause is a category error — the four existing
messages enumerate global causes and cannot name a name. What an empty state CAN do
honestly is state the **scope that was searched**.

⭐⭐ **And the reason it ranks first is not the copy.** A user seeing
*"2,286 with bars today"* on a day when that is normally ~2,290 sees nothing; a user
seeing **1,847** sees the breadth collapse that the 6.8.6 feed alarm was structurally
blind to, because that alarm asserts RECENCY and this asserts COVERAGE. **A second,
independent detector for the defect that caused the whole universe rebuild — as a side
effect of fixing a message.** That is why `breadth_median` ships alongside the count: a
bare number cannot be judged, and A24 says a figure without its reference is decoration.

⚠ **THE FUNNEL IS NESTED, AND THAT CONSTRAINED THE DESIGN.** "names with a bar today" is
**2,637** — LARGER than the 2,291-name universe — because D3 made the archive ingest every
known NSE symbol regardless of tradeability. Rendering that as stage 3 would show a funnel
widening, which reads as a bug. So the bar stage is **scoped to the universe**: *of the
names we would trade, how many priced today*. That is both nested and the number breadth
detection actually needs.

⛔ **"assessed" is DELIBERATELY ABSENT, not zero.** Nothing counts how many panels the
scorer evaluated — it is not persisted anywhere. Rather than fabricate a rung, the stage
is omitted and `assessed_available` says so, because **a funnel with a silent missing rung
invites the reader to assume it is zero**, which is worse than four honest stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text

# ⭐ W5 — the scan OWNS this threshold; the funnel reports the stage it creates. A
# hardcoded 50 here would drift from the gate it is meant to describe.
from app.services.signal_service import MIN_CANDLES_TO_SCORE

#: How far back the breadth reference looks. Long enough to span a quiet week, short
#: enough that a structural change in the universe does not haunt the median for months.
BREADTH_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class Funnel:
    """Each stage is a COUNT with its own meaning; they are nested by construction."""

    known: int
    """Every stock row we hold, including archive-only names we would never trade."""

    in_universe: int
    """Passing the universe rule — what the scanner is allowed to look at."""

    priced_today: int
    """...and which of those actually printed a bar on the latest session."""

    admitted_to_scoring: int
    """...and which of THOSE carry enough history for the scan to score at all.

    ⭐⭐ ROUND 5 ADDED THIS RUNG, and it is the difference between an honest funnel and a
    misleading one. `signal_service` refuses any name with fewer than
    `MIN_CANDLES_TO_SCORE` completed daily candles BEFORE scoring. With four rungs the
    whole drop from `priced_today` to `signals_live` is forced onto the confluence gate,
    because the gate is the only mechanism left to explain it — so "the engine looked at
    2,286 names and liked none" renders identically to "the engine never looked at 184 of
    them". Measured 2026-09-14: **184 of 2,286 (8%) die here, unseen.**"""

    signals_live: int
    """...and which produced a signal that is not expired or withdrawn."""

    session: date | None
    """The session `priced_today` refers to. Without it the count means nothing."""

    breadth_median: int | None
    """Median `priced_today` over the lookback — the reference that makes the count
    judgeable. ⚠ Computed with TODAY's universe against past sessions, so it is a
    tripwire, not a historical series."""

    assessed_available: bool = False
    """⛔ Always False today, and it now means something NARROWER than it used to.

    `admitted_to_scoring` is computable, so the ADMISSION stage is no longer missing. What
    remains unknown is whether the scorer actually ran to completion on each admitted name
    — it persists no panel count. ⇒ the residual `admitted → signals_live` drop is still
    not fully attributable, and the UI must keep saying so rather than crediting it all to
    the gate."""

    @property
    def breadth_shortfall_pct(self) -> float | None:
        """How far below the reference today's breadth sits, or None if unjudgeable."""
        if not self.breadth_median:
            return None
        return round((1.0 - self.priced_today / self.breadth_median) * 100.0, 1)


_SQL = """
WITH latest AS (
    SELECT max((time AT TIME ZONE 'UTC')::date) AS d FROM ohlcv_1d
),
per_session AS (
    SELECT (o.time AT TIME ZONE 'UTC')::date AS d, count(DISTINCT o.stock_id) AS n
      FROM ohlcv_1d o
      JOIN stocks s ON s.id = o.stock_id AND s.is_active
     WHERE o.time > now() - make_interval(days => :lookback)
     GROUP BY 1
)
SELECT
    (SELECT count(*) FROM stocks)                              AS known,
    (SELECT count(*) FROM stocks WHERE is_active)              AS in_universe,
    (SELECT n FROM per_session WHERE d = (SELECT d FROM latest)) AS priced_today,
    (SELECT count(*) FROM (
        SELECT o.stock_id
          FROM ohlcv_1d o
          JOIN stocks s ON s.id = o.stock_id AND s.is_active
         WHERE o.stock_id IN (
               SELECT DISTINCT o2.stock_id FROM ohlcv_1d o2
                WHERE (o2.time AT TIME ZONE 'UTC')::date = (SELECT d FROM latest))
         GROUP BY o.stock_id
        HAVING count(*) >= :min_candles) q)                    AS admitted,
    (SELECT count(*) FROM signals
      WHERE status = 'active' AND quarantined_at IS NULL)      AS signals_live,
    (SELECT d FROM latest)                                     AS session,
    (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY n) FROM per_session) AS med
"""


async def load_funnel(db: Any, *, lookback_days: int = BREADTH_LOOKBACK_DAYS) -> Funnel:
    row = (
        await db.execute(
            text(_SQL),
            {"lookback": lookback_days, "min_candles": MIN_CANDLES_TO_SCORE},
        )
    ).first()
    if row is None:  # pragma: no cover - an empty database
        return Funnel(0, 0, 0, 0, 0, None, None)
    return Funnel(
        known=int(row.known or 0),
        in_universe=int(row.in_universe or 0),
        priced_today=int(row.priced_today or 0),
        admitted_to_scoring=int(row.admitted or 0),
        signals_live=int(row.signals_live or 0),
        session=row.session,
        breadth_median=int(row.med) if row.med is not None else None,
    )
