"""Signal-outcome persistence (Phase 3, slice 3.6).

SQL for the outcome recorder (alerts-stream consumer) and the expiry
finalizer. All writes are idempotent single-statement UPDATEs with
WHERE guards — the stream is at-least-once, so every operation must
tolerate redelivery; first-touch fields only ever go NULL → value, and
terminal statuses never reopen (the monotonic ladder in
models/signal.py SignalOutcome).

Touch semantics:
  - entry_zone alert  → entry_touched_at/price; status open → entry_touched
    (only while the touch is inside validity).
  - sl_touch alert    → sl_touched_at/price; status entry_touched → sl_first
    (resolution requires a PRIOR entry touch — a cross on a never-entered
    setup is a missed trade, not a loss).
  - tp_touch alert    → tp_touched_at/price; status entry_touched → tp_first.
  - First-touch STAMPS record even outside validity or without entry
    (Phase-6 honesty); only STATUS transitions are validity-guarded.

Never feeds scoring, sizing, gating, or backtests.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)

# Alert sources this module understands (live_levels meta "source").
TOUCH_SOURCES = ("entry_zone", "sl_touch", "tp_touch")

# The recorder started observing at the 3.6 deployment. Signals whose
# validity ended BEFORE this were never watched — seeding them
# expired_untouched would fabricate an observation that never happened
# (bug-hunter LOW 2026-07-19). Straddlers (valid across the epoch) are
# recorded from PARTIAL observation and their bias direction is UNKNOWN
# (a pre-epoch stop-out followed by a post-epoch TP records tp_first):
# Phase-6 headline hit-rates MUST cohort on
# signals.created_at >= OUTCOME_EPOCH (quant-verifier 2026-07-19).
OUTCOME_EPOCH = datetime(2026, 7, 19, tzinfo=UTC)


async def ensure_outcome_row(db: Any, signal_id: str) -> bool:
    """Seed the outcome row from the signal (idempotent). Returns True
    when the signal exists (row present after the call)."""
    result = await db.execute(
        text(
            "INSERT INTO signal_outcomes"
            " (signal_id, stock_id, direction, classification, timeframe,"
            "  validity_until, status)"
            " SELECT s.id, s.stock_id, s.direction, s.classification,"
            "        s.timeframe, s.validity_until, 'open'"
            " FROM signals s WHERE s.id = :sid"
            " ON CONFLICT (signal_id) DO NOTHING"
            " RETURNING signal_id"
        ),
        {"sid": signal_id},
    )
    if result.fetchone() is not None:
        return True
    exists = await db.execute(
        text("SELECT 1 FROM signal_outcomes WHERE signal_id = :sid"),
        {"sid": signal_id},
    )
    return exists.fetchone() is not None


async def apply_touch(
    db: Any, *, signal_id: str, source: str, ts: datetime, price: str
) -> None:
    """Record one touch alert (idempotent). `price` is the alert's
    Decimal string; ts the exchange-time touch stamp."""
    if source == "entry_zone":
        await db.execute(
            text(
                "UPDATE signal_outcomes SET"
                " entry_touched_at = COALESCE(entry_touched_at, :ts),"
                " entry_touch_price = COALESCE(entry_touch_price, :price),"
                " updated_at = now()"
                " WHERE signal_id = :sid"
            ),
            {"sid": signal_id, "ts": ts, "price": price},
        )
        await db.execute(
            text(
                "UPDATE signal_outcomes SET status = 'entry_touched',"
                " updated_at = now()"
                " WHERE signal_id = :sid AND status = 'open'"
                " AND :ts <= validity_until"
            ),
            {"sid": signal_id, "ts": ts},
        )
        # Crash-window upgrade (monotonic TOWARD TRUTH, never back to a
        # live state): a PEL-recovered in-validity entry touch that the
        # sweeper already finalized past proves the setup WAS entered.
        await db.execute(
            text(
                "UPDATE signal_outcomes SET status = 'expired_open',"
                " updated_at = now()"
                " WHERE signal_id = :sid AND status = 'expired_untouched'"
                " AND :ts <= validity_until"
            ),
            {"sid": signal_id, "ts": ts},
        )
        return

    if source not in ("sl_touch", "tp_touch"):
        return
    col = "sl" if source == "sl_touch" else "tp"
    resolved = "sl_first" if source == "sl_touch" else "tp_first"
    await db.execute(
        text(
            f"UPDATE signal_outcomes SET"  # noqa: S608 — col from a literal map
            f" {col}_touched_at = COALESCE({col}_touched_at, :ts),"
            f" {col}_touch_price = COALESCE({col}_touch_price, :price),"
            " updated_at = now()"
            " WHERE signal_id = :sid"
        ),
        {"sid": signal_id, "ts": ts, "price": price},
    )
    # Resolution: only with a prior entry touch, only inside validity,
    # and only once. 'entry_touched' is the live path; 'expired_open'
    # is the crash-window upgrade (sweeper finalized while the touch
    # sat unacked in the PEL) — both prove the same in-validity truth.
    # ":ts >= entry_touched_at" pins the ORDER: a redelivered PRE-entry
    # touch must never resolve after the entry lands (quant-verifier
    # HIGH 2026-07-19 — a TP you couldn't have taken is not a win; the
    # PEL reorder path made it reachable).
    await db.execute(
        text(
            "UPDATE signal_outcomes SET status = :resolved, resolved_at = :ts,"
            " updated_at = now()"
            " WHERE signal_id = :sid"
            " AND (status = 'entry_touched'"
            "      OR (status = 'expired_open' AND entry_touched_at IS NOT NULL))"
            " AND :ts <= validity_until"
            " AND :ts >= entry_touched_at"
        ),
        {"sid": signal_id, "resolved": resolved, "ts": ts},
    )


async def finalize_expired_outcomes(db: Any, now: datetime | None = None) -> int:
    """Close the books on lapsed signals (expiry sweeper hook):
    - seed missing rows for signals already past validity (a signal that
      never fired a single alert still deserves an expired_untouched row);
    - non-terminal rows past validity → expired_untouched / expired_open.
    Returns the number of rows moved to a terminal status."""
    now = now or datetime.now(tz=UTC)
    await db.execute(
        text(
            "INSERT INTO signal_outcomes"
            " (signal_id, stock_id, direction, classification, timeframe,"
            "  validity_until, status)"
            " SELECT s.id, s.stock_id, s.direction, s.classification,"
            "        s.timeframe, s.validity_until, 'open'"
            " FROM signals s"
            " WHERE s.validity_until <= :now"
            " AND s.validity_until >= :epoch"
            " AND NOT EXISTS (SELECT 1 FROM signal_outcomes o"
            "                 WHERE o.signal_id = s.id)"
        ),
        {"now": now, "epoch": OUTCOME_EPOCH},
    )
    # Classify on the LADDER, not the raw stamp: stamps deliberately
    # record even outside validity (Phase-6 honesty), so a late touch on
    # a still-open row must finalize as expired_UNTOUCHED (bug-hunter
    # MEDIUM 2026-07-19, executed repro). `status` already encodes
    # "touched inside validity".
    result = await db.execute(
        text(
            "UPDATE signal_outcomes SET"
            " status = CASE WHEN status = 'open'"
            "          THEN 'expired_untouched' ELSE 'expired_open' END,"
            " resolved_at = :now, updated_at = now()"
            " WHERE status IN ('open', 'entry_touched')"
            " AND validity_until <= :now"
            " RETURNING signal_id"
        ),
        {"now": now},
    )
    return len(result.fetchall())
