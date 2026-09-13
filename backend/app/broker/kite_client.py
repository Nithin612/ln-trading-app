"""Zerodha KiteConnect client wrapper.

Responsibilities:
- Build the Kite login URL (step 1 of OAuth)
- Exchange request_token for access_token (step 2)
- Persist/revoke BrokerToken rows in the DB
- Download and upsert the instruments CSV into kite_instruments

Rate-limited REST (historical data) does NOT live here: it goes through
`app.broker.kite_rest.ThrottledKite` — the shared throttled client
(trading-domain.md). The unthrottled `fetch_historical` that used to
live in this module was the 2026-07-13 rebuild's failure root and was
removed 2026-07-17. `build_kite` remains for one-shot or
explicitly-batched low-rate calls (instruments CSV, session exchange,
the per-minute F&O chain snapshot in app/tasks/fo_tasks.py).
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx
from kiteconnect import KiteConnect
from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.broker import BrokerToken, KiteInstrument

log = logging.getLogger(__name__)

# Kite tokens expire at 6 AM IST the next day.
# Store that offset (UTC equivalent of 6 AM IST = 0:30 UTC).
_TOKEN_EXPIRY_HOUR_UTC = 0
_TOKEN_EXPIRY_MINUTE_UTC = 30


def _next_expiry() -> datetime:
    """Return UTC datetime for 6 AM IST tomorrow."""
    now_utc = datetime.now(UTC)
    expiry = now_utc.replace(
        hour=_TOKEN_EXPIRY_HOUR_UTC,
        minute=_TOKEN_EXPIRY_MINUTE_UTC,
        second=0,
        microsecond=0,
    )
    if expiry <= now_utc:
        expiry += timedelta(days=1)
    return expiry


def get_login_url() -> str:
    """Return the Zerodha login redirect URL for step 1 of OAuth."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    return str(kc.login_url())


async def exchange_token(
    db: AsyncSession,
    user_id: int,
    request_token: str,
) -> BrokerToken:
    """Exchange request_token for access_token, persist, and return the BrokerToken row."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    data: dict[str, Any] = kc.generate_session(
        request_token, api_secret=settings.kite_api_secret
    )
    access_token: str = data["access_token"]

    # Invalidate any existing active tokens for this user
    await db.execute(
        update(BrokerToken)
        .where(BrokerToken.user_id == user_id, BrokerToken.is_active.is_(True))
        .values(is_active=False)
    )

    token = BrokerToken(
        user_id=user_id,
        broker="kite",
        access_token=access_token,
        request_token=request_token,
        expires_at=_next_expiry(),
        is_active=True,
    )
    db.add(token)
    await db.flush()
    await db.refresh(token)
    log.info("Kite access_token stored for user_id=%d expires=%s", user_id, token.expires_at)
    return token


async def get_active_token(db: AsyncSession, user_id: int) -> BrokerToken | None:
    """Return the current active, non-expired BrokerToken for this user, or None."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(BrokerToken)
        .where(
            BrokerToken.user_id == user_id,
            BrokerToken.is_active.is_(True),
            BrokerToken.expires_at > now,
        )
        .order_by(BrokerToken.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def build_kite(access_token: str) -> KiteConnect:
    """Return a KiteConnect instance ready for REST API calls."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    kc.set_access_token(access_token)
    return kc


def map_instrument_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter + normalize raw Kite instrument rows for kite_instruments.

    Kept: NSE/BSE cash instruments AND the NFO derivatives segment (futures +
    options, with strike) — the option-chain recorder selects instruments
    from these rows locally instead of hitting Kite per request.
    """
    records: list[dict[str, Any]] = []
    for r in rows:
        exchange = str(r.get("exchange", ""))
        instrument_type = str(r.get("instrument_type", ""))
        if exchange not in ("NSE", "BSE", "NFO"):
            continue
        try:
            records.append(
                {
                    "instrument_token": int(r["instrument_token"]),
                    "exchange_token": int(r["exchange_token"]),
                    "tradingsymbol": str(r["tradingsymbol"]),
                    "exchange": exchange,
                    "instrument_type": instrument_type,
                    "name": str(r.get("name", "")),
                    "last_price": float(r.get("last_price", 0) or 0),
                    "tick_size": float(r.get("tick_size", 0.05) or 0.05),
                    "lot_size": int(r.get("lot_size", 1) or 1),
                    "segment": str(r.get("segment", "")),
                    "expiry": str(r.get("expiry", "") or ""),
                    "strike": Decimal(str(r.get("strike", 0) or 0)),
                    "synced_at": datetime.now(UTC),
                }
            )
        except (KeyError, ValueError, TypeError, InvalidOperation):
            # Decimal("garbage") raises InvalidOperation, int(None) raises
            # TypeError — neither is a ValueError (bug-hunter LOW,
            # 2026-07-17: one malformed strike used to crash the sync).
            continue  # skip malformed rows
    return records


# Partial-dump tripwire for the stale sweep: a truncated instruments CSV
# must never mass-delete good rows. The tradable universe never halves
# day-over-day (largest real cliff: monthly NFO expiry ≈ 28% of the
# dump); anything below this fraction is a bad download.
_SWEEP_MIN_FRACTION = 0.5
# Hard-sweep horizon: a row absent from EVERY dump for this many days
# cannot be explained by any truncated download. Hard-deleting those
# BEFORE the fraction guard computes its denominator keeps the guard
# from self-wedging once stale ≥ live (bug-hunter MEDIUM, 2026-07-17:
# after a long sync lapse or a mass token rotation, the single-tier
# guard would skip the sweep forever — blocking the only mechanism that
# could shrink its own denominator).
_HARD_SWEEP_DAYS = 7

# ⭐ U1 — the instruments dump is PUBLIC, and that is what lets it have a
# SCHEDULED owner. Kite access tokens die ~06:00 IST daily and can only be
# renewed through an interactive OAuth login, so a beat task that required
# one would fail exactly as often as the login is forgotten — which is the
# failure that left `kite_instruments` EMPTY for five days (2026-09-07 →
# 09-12) and the live worker running dark with `up: 0 instruments`.
# Measured 2026-09-13: this URL returns HTTP 200 with 110,290 rows and no
# Authorization header. The authenticated SDK path is kept for the admin
# endpoint, which already holds a token.
_INSTRUMENTS_URL = "https://api.kite.trade/instruments"
_INSTRUMENTS_TIMEOUT_S = 120.0


async def _delete_older_than(db: AsyncSession, cutoff: datetime) -> int:
    result = cast(
        "CursorResult[Any]",
        await db.execute(delete(KiteInstrument).where(KiteInstrument.synced_at < cutoff)),
    )
    return result.rowcount


async def sync_instruments(db: AsyncSession, access_token: str | None = None) -> int:
    """Download instruments CSV from Kite, upsert into kite_instruments,
    then SWEEP rows absent from the dump.

    `access_token=None` uses the PUBLIC dump (`_INSTRUMENTS_URL`) instead of
    the authenticated SDK call. That is what makes a scheduled owner possible
    — see `_INSTRUMENTS_URL`. Both paths parse the same CSV and produce the
    same rows; only the transport differs.

    The dump is Kite's complete tradable universe for the kept segments
    (NSE/BSE/NFO): a row missing from it is DEAD — delisted equity, moved
    exchange, or expired derivative. Upsert-only sync let those carcasses
    accumulate (synced_at frozen at the last dump containing them) and
    keep JOINing into the worker's subscription universe, where every
    REST call against them fails `invalid token` (the 07-14/15 repair
    failures: 16 stocks; 1,584 stale rows by 2026-07-17).

    Two-tier sweep: rows absent ≥ _HARD_SWEEP_DAYS are deleted
    unconditionally, THEN the fraction guard decides whether this run's
    younger absences may be swept (skip + WARN on a suspected partial
    dump — young stale rows survive until a full dump arrives).

    Returns the number of rows upserted (sweep counts are logged).
    """
    def _download_and_parse() -> list[Any]:
        if not access_token:
            # Public path — no Authorization header, no token lifetime.
            resp = httpx.get(
                _INSTRUMENTS_URL, timeout=_INSTRUMENTS_TIMEOUT_S, follow_redirects=True
            )
            resp.raise_for_status()
            return list(csv.DictReader(io.StringIO(resp.text)))
        kc = build_kite(access_token)
        # kiteconnect returns raw CSV bytes from instruments(); newer SDK
        # versions return a parsed list.
        raw: bytes | str = kc.instruments()
        if isinstance(raw, (list, dict)):
            return list(raw)
        reader = csv.DictReader(io.StringIO(raw if isinstance(raw, str) else raw.decode()))
        return list(reader)

    # Multi-MB blocking download + parse + 60k-row mapping loop: off the
    # event loop — the tick consumer can share this loop (bug-hunter
    # MEDIUM, 2026-07-17: an admin-triggered mid-session sync used to
    # stall tick processing for seconds).
    rows = await asyncio.to_thread(_download_and_parse)

    # ⛔ Both emptiness checks RAISE rather than return 0 (bug-hunter, 2026-09-13).
    # A dump host that answers HTTP 200 with a login interstitial or an error page
    # passes `raise_for_status()`, parses into junk-keyed rows, and maps to zero
    # records — so the old `return 0` reported SUCCESS to a Celery task that then
    # logged "kite_instruments refreshed: 0 rows" every weekday forever while the
    # table went stale. That is the same "success log over work that did not
    # happen" class as the missing commit above, reached through the next door.
    # Raising is safe: a genuine dump can never contain zero NSE/BSE/NFO rows, and
    # both checks sit BEFORE every write, so nothing is half-applied or swept.
    if not rows:
        raise RuntimeError(
            f"instruments dump was empty ({'public URL' if not access_token else 'SDK'}) "
            "— refusing to report success; kite_instruments left untouched"
        )

    records = await asyncio.to_thread(map_instrument_rows, rows)
    if not records:
        raise RuntimeError(
            f"instruments dump parsed {len(rows)} rows but kept 0 — this is not a Kite "
            "instruments CSV (login/interstitial page, or a column rename). Refusing to "
            "report success; kite_instruments left untouched"
        )

    # Watermark derived from the data itself: "no fresh row below the
    # watermark" holds by construction even across a backward clock step
    # during mapping (rows AT the watermark survive the strict <).
    watermark = min(r["synced_at"] for r in records)

    # Chunked upsert: with NFO included this is ~80k rows — a single VALUES
    # clause would exceed asyncpg's bind-parameter limit.
    chunk = 2000
    for i in range(0, len(records), chunk):
        stmt = pg_insert(KiteInstrument).values(records[i : i + chunk])
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_token"],
            set_={
                "last_price": stmt.excluded.last_price,
                "synced_at": stmt.excluded.synced_at,
                "tradingsymbol": stmt.excluded.tradingsymbol,
                "name": stmt.excluded.name,
                "expiry": stmt.excluded.expiry,
                "strike": stmt.excluded.strike,
            },
        )
        await db.execute(stmt)

    hard = await _delete_older_than(db, watermark - timedelta(days=_HARD_SWEEP_DAYS))

    total = (
        await db.execute(select(func.count()).select_from(KiteInstrument))
    ).scalar_one()
    if len(records) < _SWEEP_MIN_FRACTION * total:
        log.warning(
            "instrument sweep SKIPPED: dump has %d rows vs %d in table — "
            "partial dump suspected, young stale rows kept for this run",
            len(records), total,
        )
        deleted = 0
    else:
        deleted = await _delete_older_than(db, watermark)

    # ⛔ U1 (2026-09-13): this function used to rely on its caller to commit.
    # The only caller was the admin endpoint, whose `get_db` dependency
    # auto-commits — so it worked, invisibly, for one caller only. The moment a
    # Celery task called it, `run_db_task` (which does NOT commit) rolled the
    # whole sync back while the log below still reported success: 57,595 rows
    # "synced" into an empty table. Upsert + sweep is one unit of work and owns
    # its own commit, matching `bhavcopy_service.upsert_bhavcopy_rows`.
    await db.commit()

    log.info(
        "Kite instruments synced: %d rows upserted, %d stale swept (%d hard)",
        len(records), deleted + hard, hard,
    )
    return len(records)
