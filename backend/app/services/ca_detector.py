"""Corporate-action discontinuity detector (Phase 2 slice 6).

Raw bhavcopy history is unadjusted: a split/bonus shows up as a huge
overnight "gap" that would poison every indicator window. Policy
(ARCHITECTURE.md §Corporate actions): DETECT and QUARANTINE — never
auto-adjust and never trade a poisoned window. Flagged stocks are excluded
from universe resolution until manually reviewed (unflag via admin after
verifying the data or re-fetching adjusted history).

Heuristic: |open ÷ prev_close − 1| > threshold (default 20%) between two
consecutive TRADING sessions. Genuine 20%-circuit moves are rarer than
splits at this threshold; false positives cost a review, false negatives
cost a poisoned window — the asymmetry favors flagging.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

DISCONTINUITY_THRESHOLD_PCT = 20.0


async def scan_for_discontinuities(
    db: AsyncSession,
    session_date: date,
    threshold_pct: float = DISCONTINUITY_THRESHOLD_PCT,
) -> list[tuple[int, str]]:
    """Flag active stocks whose `session_date` open gaps more than
    `threshold_pct` from the previous session's close. Returns
    [(stock_id, reason)] for the newly flagged."""
    rows = (
        await db.execute(
            text(
                """
                WITH latest AS (
                    SELECT o.stock_id, o.time::date AS d, o.open,
                           LAG(o.close) OVER (PARTITION BY o.stock_id ORDER BY o.time)
                               AS prev_close
                    FROM ohlcv_1d o
                    WHERE o.time::date <= :session_date
                      AND o.time::date >= :session_date - INTERVAL '14 days'
                )
                SELECT l.stock_id, l.open, l.prev_close
                FROM latest l
                JOIN stocks s ON s.id = l.stock_id
                WHERE l.d = :session_date
                  AND l.prev_close IS NOT NULL AND l.prev_close > 0
                  AND s.is_active AND s.ca_flagged_at IS NULL
                  AND ABS(l.open / l.prev_close - 1) > :threshold
                """
            ),
            {"session_date": session_date, "threshold": threshold_pct / 100.0},
        )
    ).fetchall()

    flagged: list[tuple[int, str]] = []
    now = datetime.now(tz=UTC)
    for r in rows:
        gap_pct = (float(r.open) / float(r.prev_close) - 1.0) * 100.0
        reason = (
            f"{session_date}: open {float(r.open):.2f} vs prev close "
            f"{float(r.prev_close):.2f} ({gap_pct:+.1f}%) — possible corporate action"
        )
        await db.execute(
            text(
                "UPDATE stocks SET ca_flagged_at = :now, ca_flag_reason = :reason"
                " WHERE id = :sid"
            ),
            {"now": now, "reason": reason[:255], "sid": r.stock_id},
        )
        flagged.append((r.stock_id, reason))
        log.warning("CA quarantine: stock_id=%s %s", r.stock_id, reason)

    if flagged:
        await db.commit()
    return flagged
