"""Intraday option-chain snapshot recorder.

Every minute during market hours (Celery beat), for each configured
underlying (default NIFTY, BANKNIFTY):

  1. spot from `kite.ltp` →
  2. nearest-expiry option instruments within ±N strikes of spot, plus the
     nearest future, from the locally synced `kite_instruments` (NFO rows) →
  3. one `kite.quote` batch (≤500 instruments, well within the 1 rps REST
     budget) →
  4. idempotent insert into `option_chain_snapshots` (hypertable).

Runs in Celery (sync kiteconnect calls are fine there). Degrades silently:
no active Kite token, or NFO instruments not yet synced → status "skipped".
This module deliberately has no opinions about IV/Greeks — it only records;
analytics arrive in the F&O phase and will be Rust-side.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import KiteInstrument
from app.models.fo_data import OptionChainSnapshot

log = logging.getLogger(__name__)

# Kite's index LTP keys differ from NFO underlying names
_SPOT_KEY_BY_UNDERLYING = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
}


@dataclass
class ChainInstrument:
    instrument_token: int
    symbol: str            # underlying (NIFTY, RELIANCE, …)
    expiry_date: date
    strike: Decimal
    option_type: str       # CE | PE | FU


def spot_ltp_key(underlying: str) -> str:
    """The kite.ltp key used to fetch the spot for an underlying."""
    return _SPOT_KEY_BY_UNDERLYING.get(underlying, f"NSE:{underlying}")


async def get_any_active_admin_token(db: AsyncSession) -> str | None:
    """Newest active, unexpired broker token belonging to an admin, or None."""
    result = await db.execute(
        text(
            "SELECT bt.access_token FROM broker_tokens bt"
            " JOIN users u ON u.id = bt.user_id"
            " WHERE bt.is_active = true AND bt.expires_at > now()"
            "   AND u.role = 'admin'"
            " ORDER BY bt.created_at DESC LIMIT 1"
        )
    )
    row = result.fetchone()
    return row[0] if row else None


async def select_chain_instruments(
    db: AsyncSession,
    underlying: str,
    spot: Decimal,
    strikes_each_side: int,
) -> list[ChainInstrument]:
    """Nearest-expiry CE/PE within ±N strikes of spot, plus the nearest future.

    Reads the locally synced NFO instrument dump — no network.
    """
    today_iso = datetime.now(UTC).date().isoformat()

    # Nearest upcoming option expiry for this underlying
    expiry_row = await db.execute(
        select(KiteInstrument.expiry)
        .where(
            KiteInstrument.exchange == "NFO",
            KiteInstrument.name == underlying,
            KiteInstrument.instrument_type.in_(["CE", "PE"]),
            KiteInstrument.expiry >= today_iso,
        )
        .order_by(KiteInstrument.expiry.asc())
        .limit(1)
    )
    nearest_expiry = expiry_row.scalar_one_or_none()
    if nearest_expiry is None:
        return []

    options_result = await db.execute(
        select(KiteInstrument)
        .where(
            KiteInstrument.exchange == "NFO",
            KiteInstrument.name == underlying,
            KiteInstrument.instrument_type.in_(["CE", "PE"]),
            KiteInstrument.expiry == nearest_expiry,
        )
    )
    options = list(options_result.scalars().all())
    if not options:
        return []

    # Keep the N distinct strikes nearest to spot, both sides, both types.
    strikes = sorted({o.strike for o in options}, key=lambda s: abs(s - spot))
    keep = set(strikes[: max(strikes_each_side * 2 + 1, 1)])

    chain: list[ChainInstrument] = [
        ChainInstrument(
            instrument_token=o.instrument_token,
            symbol=underlying,
            expiry_date=date.fromisoformat(o.expiry),
            strike=o.strike,
            option_type=o.instrument_type,
        )
        for o in options
        if o.strike in keep
    ]

    # Nearest future for basis/OI context
    fut_row = await db.execute(
        select(KiteInstrument)
        .where(
            KiteInstrument.exchange == "NFO",
            KiteInstrument.name == underlying,
            KiteInstrument.instrument_type == "FUT",
            KiteInstrument.expiry >= today_iso,
        )
        .order_by(KiteInstrument.expiry.asc())
        .limit(1)
    )
    fut = fut_row.scalar_one_or_none()
    if fut is not None:
        chain.append(
            ChainInstrument(
                instrument_token=fut.instrument_token,
                symbol=underlying,
                expiry_date=date.fromisoformat(fut.expiry),
                strike=Decimal("0"),
                option_type="FU",
            )
        )

    return chain


def quotes_to_rows(
    snapshot_time: datetime,
    chain: list[ChainInstrument],
    quotes: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map a kite.quote response onto option_chain_snapshots rows.

    kite.quote keyed by str(instrument_token) when queried by token.
    Depth may be absent (indices futures after hours) — tolerate.
    """
    rows: list[dict[str, Any]] = []
    for inst in chain:
        q = quotes.get(str(inst.instrument_token))
        if q is None:
            continue

        def dec(v: Any) -> Decimal | None:
            if v is None:
                return None
            try:
                return Decimal(str(v))
            except ArithmeticError:
                return None

        depth = q.get("depth") or {}
        buy = (depth.get("buy") or [{}])[0]
        sell = (depth.get("sell") or [{}])[0]

        rows.append(
            {
                "time": snapshot_time,
                "instrument_token": inst.instrument_token,
                "symbol": inst.symbol,
                "expiry_date": inst.expiry_date,
                "strike": inst.strike,
                "option_type": inst.option_type,
                "ltp": dec(q.get("last_price")),
                "bid": dec(buy.get("price")),
                "ask": dec(sell.get("price")),
                "volume": q.get("volume"),
                "oi": q.get("oi"),
            }
        )
    return rows


async def insert_snapshot_rows(db: AsyncSession, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(OptionChainSnapshot).values(rows).on_conflict_do_nothing()
    result = await db.execute(stmt)
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def record_chain_snapshots(
    db: AsyncSession,
    kite: Any,  # KiteConnect (duck-typed for tests)
    underlyings: list[str],
    strikes_each_side: int,
    snapshot_time: datetime | None = None,
) -> dict[str, Any]:
    """One recording pass across all configured underlyings."""
    snapshot_time = snapshot_time or datetime.now(UTC).replace(second=0, microsecond=0)

    spot_keys = [spot_ltp_key(u) for u in underlyings]
    try:
        ltp_map: dict[str, Any] = kite.ltp(spot_keys)
    except Exception:
        log.exception("chain recorder: spot LTP fetch failed")
        return {"status": "error", "message": "spot ltp fetch failed", "inserted": 0}

    all_rows: list[dict[str, Any]] = []
    per_underlying: dict[str, int] = {}

    for underlying in underlyings:
        spot_raw = (ltp_map.get(spot_ltp_key(underlying)) or {}).get("last_price")
        if not spot_raw:
            per_underlying[underlying] = 0
            continue
        spot = Decimal(str(spot_raw))

        chain = await select_chain_instruments(db, underlying, spot, strikes_each_side)
        if not chain:
            per_underlying[underlying] = 0
            continue

        tokens = [c.instrument_token for c in chain]
        try:
            quotes = kite.quote(tokens)  # ≤ ~90 instruments per underlying
        except Exception:
            log.exception("chain recorder: quote fetch failed for %s", underlying)
            per_underlying[underlying] = 0
            continue

        rows = quotes_to_rows(snapshot_time, chain, quotes)
        per_underlying[underlying] = len(rows)
        all_rows.extend(rows)

    inserted = await insert_snapshot_rows(db, all_rows)
    return {
        "status": "ok",
        "time": snapshot_time.isoformat(),
        "inserted": inserted,
        "per_underlying": per_underlying,
    }
