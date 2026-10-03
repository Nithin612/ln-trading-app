"""Celery task — CAS (Closing Auction Session) daily capture (Stage 1) + the post-close window.

Polls Kite /quote for the F&O (Category-I) universe during 3:15–3:35 IST and upserts one `cas_daily`
row per stock (pre-auction price, reference, indicative close, official/auction close, imbalance).
Research/observability only — the order path never reads it. Beat fires it every minute in a broad
window; the task self-guards to its windows, no-op otherwise. Silently idle without an active
Kite admin token (mirrors circuit_tasks).

Two windows, one task (W2 — the beat entry already fires every minute through 16:29 IST):
  - **CAS** 15:15–15:33 IST → `cas_daily` (unchanged).
  - **Post-close** 15:44–16:05 IST → `cas_postclose_daily` (DA-7, 2026-09-30). This brackets the
    post-close session, 15:50–16:00 at the closing price (SEBI CAS circular clause 4.2.4). The
    first poll (15:44) lands after the auction matched and before the session opens, so its
    volume is the baseline. Polls inside [15:50, 16:00) record pending buy/sell interest, and the
    last polls (after 16:00) record the final volume. It writes a separate table on purpose: if
    this code ever runs before its migration, only the post-close write fails — never the CAS
    capture.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.core.config import settings
from app.services.notifier import (
    notify_exception,
    notify_task_result,
)
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")
# CAS is 15:15–15:35 IST; auction executes ~15:29. Capture 15:15–15:33 to catch the executed close.
_CAS_START = time(15, 15)
_CAS_END = time(15, 33)
# Post-close session is 15:50–16:00 IST (SEBI CAS circular 4.2.4). Poll 15:44–16:05 so the first
# poll is a pre-session baseline and the last ones see the final volume.
_POSTCLOSE_START = time(15, 44)
_POSTCLOSE_END = time(16, 5)
_POSTCLOSE_SESSION_START = time(15, 50)
_POSTCLOSE_SESSION_END = time(16, 0)  # exclusive — the session is over at 16:00:00


def _within_cas_window() -> bool:
    now = datetime.now(UTC).astimezone(_IST).timetz().replace(tzinfo=None)
    return _CAS_START <= now <= _CAS_END


def _capture_mode(t: time) -> str | None:
    """Which capture an IST wall-clock time belongs to: "cas", "postclose", or None (idle)."""
    if _CAS_START <= t <= _CAS_END:
        return "cas"
    if _POSTCLOSE_START <= t <= _POSTCLOSE_END:
        return "postclose"
    return None


def _in_postclose_session(t: time) -> bool:
    """True inside the post-close session itself, [15:50, 16:00) IST — the only polls whose
    pending buy/sell quantities describe the session."""
    return _POSTCLOSE_SESSION_START <= t < _POSTCLOSE_SESSION_END


def _in_postclose_session_at(ts: datetime) -> bool:
    """`_in_postclose_session` for an aware instant — applied when the quote arrives."""
    return _in_postclose_session(ts.astimezone(_IST).timetz().replace(tzinfo=None))


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.cas_tasks.capture_cas_window", bind=True, max_retries=0
)
def capture_cas_window(self: object) -> dict[str, object]:  # noqa: ARG001
    """One CAS-capture pass. Beat fires it each minute in the market window; it self-guards.

    A11: the notifier is wired in the `finally`, so a crash reports even if the task dies on
    the way out. `ok` and `skipped` are silent by policy — this fires ~1,400 times a day and
    the captured rows are their own confirmation.

    ⚠ The failure this task is most exposed to is an ABSENCE — the window passing with the
    worker down, which cannot be back-filled and which no `finally` here can observe,
    because nothing runs. That alarm is A40's `scripts/cas_watch.py`, run from cron.
    """
    result: dict[str, object] = {"status": "unknown"}
    try:
        result = run_db_task(_run_capture_cas)
        return result
    except BaseException as exc:  # noqa: BLE001 — including SystemExit; see below
        # BaseException, not Exception: a wrapper kill still produces a push before the
        # process dies, which is the whole point of notifying from a `finally`.
        notify_exception("cas_capture", "CAS capture failed", exc)
        raise
    finally:
        if result.get("status") != "unknown":
            notify_task_result("cas_capture", "CAS capture", result)


async def _run_capture_cas() -> dict[str, object]:
    from sqlalchemy import select

    from app.broker.kite_rest import ThrottledKite
    from app.db.session import AsyncSessionFactory
    from app.models.stock import Stock
    from app.services.cas_capture import capture_cas, capture_postclose
    from app.services.chain_recorder import get_any_active_admin_token
    from app.services.market_calendar import is_regular_session

    if not settings.cas_capture_enabled:
        return {"status": "skipped", "message": "cas_capture_enabled is False"}
    now_ist = datetime.now(UTC).astimezone(_IST)
    wall = now_ist.timetz().replace(tzinfo=None)
    mode = _capture_mode(wall)
    if mode is None:
        return {"status": "skipped", "message": "outside the CAS and post-close windows"}

    async with AsyncSessionFactory() as db:
        if not await is_regular_session(db, now_ist.date()):  # no auction on a special session
            return {"status": "skipped", "message": "market holiday"}
        token = await get_any_active_admin_token(db)
        if token is None:
            return {"status": "skipped", "message": "no active kite token"}
        # ORDER BY id: two concurrent duplicate polls (a second, orphaned beat — it happened on
        # 2026-09-29 and again 09-30) must take row locks in the same order, or their upserts
        # can deadlock (bug-hunter LOW-4c).
        rows = (
            await db.execute(
                select(Stock.id, Stock.symbol)
                .where(Stock.is_active, Stock.is_fno)
                .order_by(Stock.id)
            )
        ).all()
        symbol_stock_map = {f"NSE:{sym}": sid for sid, sym in rows}
        if not symbol_stock_map:
            return {"status": "skipped", "message": "empty F&O universe"}
        kite = ThrottledKite(token)
        if mode == "cas":
            written = await capture_cas(db, kite, symbol_stock_map, trade_date=now_ist.date())
        else:
            written = await capture_postclose(
                db,
                kite,
                symbol_stock_map,
                trade_date=now_ist.date(),
                in_session_at=_in_postclose_session_at,
            )

    log.info(
        "CAS capture (%s): %d rows upserted over %d F&O stocks",
        mode,
        written,
        len(symbol_stock_map),
    )
    # ⭐ A poll that wrote NOTHING is not "ok" (bug-hunter MED-3): every /quote batch failing is
    # logged per batch and skipped, and "ok" is silent by notifier policy — so a whole post-close
    # session could vanish with no alarm, and A40 only counts cas_daily. "empty" is a WARNING.
    status = "ok" if written > 0 else "empty"
    return {"status": status, "mode": mode, "written": written, "universe": len(symbol_stock_map)}
