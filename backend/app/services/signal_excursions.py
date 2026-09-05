"""Signal-level MFE/MAE recorder (Phase 6 slice 6.1).

Populates each *terminal* ``signal_outcome`` with the max-favourable / max-
adverse excursion over the signal's validity window, computed from the 1m tape
via the shared ``excursion`` primitives. Anchored at the SIGNAL's planned
``entry_price`` (setup-level, not fill-level), so 6.2 can ask "did this SETUP
have edge?" — first-touch ordering alone cannot separate a bad *setup* from a
bad *stop*, and those need opposite fixes.

No look-ahead: bars are ``is_complete`` 1m candles within
``[signal.created_at, end]``, where ``end`` is capped at ``validity_until`` — a
swept row's ``resolved_at`` is the SWEEP time (later than validity), so it must
never widen the window. Idempotent: only terminal, not-yet-computed rows in the
``OUTCOME_EPOCH`` cohort are touched, each stamped ``excursion_computed_at``.

Pure observability: never feeds scoring, sizing, gating, or backtests.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratios import MAX_R, clamp_ratio
from app.services.excursion import load_1m_bars, tape_excursion
from app.services.signal_outcomes import OUTCOME_EPOCH

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

# BUY/SELL (the signal's direction) → LONG/SHORT (the excursion convention).
# Passing "BUY" straight to tape_excursion would read as SHORT and invert
# MFE/MAE — the mapping is mandatory.
_SIDE = {"BUY": "LONG", "SELL": "SHORT"}

# mfe_r/mae_r persist as Numeric(7,3) (±9999.999). R = move/risk is unbounded as
# risk → 0 (a signal with a near-zero natural SL), so winsorize at the column
# bound before persisting: an overflow would abort the batch commit, the failing
# row would never stamp excursion_computed_at, and it would be re-selected +
# re-fail every 5-min sweep — poisoning the whole backlog behind it. Any
# |R| ≥ 10000 is a near-zero-risk artifact, not an edge, so capping it there
# loses nothing 6.2 would trust (the raw value is logged when it happens).
# The bound itself now lives in app/core/ratios.MAX_R (H6) — it was duplicated
# verbatim in pair_outcome, and two OTHER modules carried a 1000×-smaller constant
# doing a different job (the expectancy winsor).


def _clip_r(r: Decimal) -> Decimal:
    return clamp_ratio(r, MAX_R)


async def _stamp(db: AsyncSession, signal_id: str, now: datetime) -> int:
    """Retire a row — mark computed, leave the excursion NULL (no tape, or an
    unmappable direction) — and commit it. Returns 1 only if THIS call stamped it
    (0 if an overlapping sweep already did), so the caller's count stays honest."""
    res = await db.execute(
        text(
            "UPDATE signal_outcomes SET excursion_computed_at = :now, updated_at = now()"
            " WHERE signal_id = :sid AND excursion_computed_at IS NULL"
        ),
        {"sid": signal_id, "now": now},
    )
    await db.commit()
    return 1 if getattr(res, "rowcount", 0) else 0


async def compute_outcome_excursions(
    db: AsyncSession,
    *,
    since: datetime = OUTCOME_EPOCH,
    limit: int | None = 200,
    now: datetime | None = None,
) -> int:
    """Fill MFE/MAE for terminal, not-yet-computed outcomes in the cohort.

    Returns the count marked computed this call. Bounded by ``limit`` per call
    (the 5-min expiry beat drains the backlog over successive runs; the backfill
    script passes ``limit=None``). Idempotent — safe to re-run.
    """
    now = now or datetime.now(tz=UTC)
    lim = "" if limit is None else f" LIMIT {int(limit)}"
    rows = (
        await db.execute(
            text(
                "SELECT o.signal_id, o.stock_id, o.direction, o.validity_until,"
                "       o.resolved_at, s.entry_price, s.stop_loss, s.created_at"
                "  FROM signal_outcomes o"
                "  JOIN signals s ON s.id = o.signal_id"
                " WHERE o.excursion_computed_at IS NULL"
                # Terminal only: a still-open window has price yet to come. The
                # literal set is an internal constant (no user input).
                "   AND o.status IN"
                "       ('tp_first', 'sl_first', 'expired_untouched', 'expired_open')"
                "   AND s.created_at >= :since"
                # Effective window-end (matches the defer decision below): a
                # ready row — its end has passed — sorts ahead of one still
                # 'today' (deferred, no tape yet), so the LIMIT is spent on
                # processable rows. A same-day deferred tail can't starve ready
                # rows or early-exit the backfill (bug-hunter MEDIUM).
                " ORDER BY LEAST(o.validity_until,"
                "                COALESCE(o.resolved_at, o.validity_until)) ASC" + lim
            ),
            {"since": since},
        )
    ).all()

    computed = 0
    for r in rows:
        side = _SIDE.get((r.direction or "").upper())
        if side is None:
            # Retire an unmappable row (stamp, leave excursion NULL) so it is not
            # re-selected + re-logged every sweep. Cannot occur given the
            # BUY/SELL NOT NULL domain — defensive.
            log.warning("signal %s: unknown direction %r — retired", r.signal_id, r.direction)
            computed += await _stamp(db, r.signal_id, now)
            continue
        entry = Decimal(str(r.entry_price))
        risk = abs(entry - Decimal(str(r.stop_loss)))
        # Window: mint (N+1 bars onward) → the earlier of resolution and
        # validity. A swept row's resolved_at is the SWEEP time (> validity), so
        # it never widens the window past validity_until.
        start = r.created_at
        end = r.validity_until
        if r.resolved_at is not None and r.resolved_at < end:
            end = r.resolved_at
        bars = await load_1m_bars(db, r.stock_id, start, end)
        exc = tape_excursion(bars, side=side, entry=entry, risk=risk, quantity=1)

        if exc is None:
            # No tape for the window. Only give up (mark computed, leave the
            # excursion NULL) once the window's IST day has fully passed — else
            # a same-day intraday row would freeze before its 1m tape finished
            # ingesting, and lose its excursion forever.
            if end.astimezone(_IST).date() >= now.astimezone(_IST).date():
                continue
            computed += await _stamp(db, r.signal_id, now)
            continue

        mfe_r = _clip_r(exc.mfe_r)
        mae_r = _clip_r(exc.mae_r)
        if mfe_r != exc.mfe_r or mae_r != exc.mae_r:
            log.warning(
                "signal %s: excursion R clamped at column bound"
                " (raw mfe_r=%s mae_r=%s) — near-zero risk?",
                r.signal_id, exc.mfe_r, exc.mae_r,
            )
        res = await db.execute(
            text(
                "UPDATE signal_outcomes SET"
                " mfe_price = :mfe_price, mfe_at = :mfe_at, mfe_r = :mfe_r,"
                " mae_price = :mae_price, mae_at = :mae_at, mae_r = :mae_r,"
                " excursion_computed_at = :now, updated_at = now()"
                " WHERE signal_id = :sid AND excursion_computed_at IS NULL"
            ),
            {
                "sid": r.signal_id,
                "mfe_price": exc.mfe_price,
                "mfe_at": exc.mfe_time,
                "mfe_r": mfe_r,
                "mae_price": exc.mae_price,
                "mae_at": exc.mae_time,
                "mae_r": mae_r,
                "now": now,
            },
        )
        # Commit per row: a positional signal's tape window can be ~11k 1m bars
        # and a batch is up to `limit` rows, so committing once at the end would
        # hold write-locks on signal_outcomes across the whole batch and stall
        # the outcome recorder / Timescale maintenance (bug-hunter MEDIUM). Count
        # only a real write — a redelivered/overlapping sweep's guarded UPDATE is
        # a 0-row no-op and must not inflate the reported count (bug-hunter LOW).
        await db.commit()
        if getattr(res, "rowcount", 0):
            computed += 1

    return computed
