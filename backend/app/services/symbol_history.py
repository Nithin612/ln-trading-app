"""D1′ — recording identity churn, and refusing to overwrite an identity anchor.

⛔ **Two kinds of churn exist; one was handled and left no trace, the other was not
handled at all.**

**RENAME** — ISIN keeps, symbol changes. `seed_stocks.plan_renames` already applies
these IN PLACE so the row keeps its id and with it every bar, signal and position
(AMIRCHAND → AEROPLANE). Correct — and afterwards **nothing recorded that the old
ticker ever existed**, so "what was this id called in July?" was unanswerable. That
is half of why §20/2's reversal SQL resolves to the wrong companies.

**REUSE** — symbol keeps, ISIN changes. NSE re-issues a delisted ticker to a
different company. This fell through to the upsert's
`isin = COALESCE(EXCLUDED.isin, stocks.isin)`, which **overwrote the anchor and
merged two companies into one row** — the new company inheriting the dead one's id
and its whole price history, silently.

⚠ **The frequency of REUSE cannot be measured retrospectively**: the merge
overwrites its own evidence, so "0 ISIN mismatches today" proves nothing (our master
was rebuilt from the very CSV it is compared against). That is exactly why the
response here is *record and refuse*, not *restructure*: `uq_stocks_symbol_exchange`
still stands, because 14 queries assume one row per symbol and a schema change that
large needs a measured reason rather than a plausible one.

⭐ **The rule this module enforces: an identity anchor is filled once and never
silently rewritten.** A differing ISIN on a known symbol is EITHER a reuse or a data
correction, and nothing in the feed distinguishes them — so the existing value is
kept, the conflict is recorded, and a human decides. Silently picking either answer
is how one company inherits another's history.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)

REASON_SEED = "seed"
REASON_RENAME = "rename"
REASON_REUSE = "reuse"


def classify_isin_change(existing: str | None, incoming: str | None) -> str:
    """Pure: what an incoming ISIN means for a symbol we already know.

    `unchanged` — same, or the feed has nothing to add.
    `fill`      — we had none and the feed supplies one. Safe to write.
    `reuse`     — both present and DIFFERENT. Never written automatically.
    """
    if not incoming or existing == incoming:
        return "unchanged"
    if not existing:
        return "fill"
    return REASON_REUSE


async def open_interval(
    db: Any,
    *,
    stock_id: int,
    symbol: str,
    exchange: str,
    isin: str | None,
    on: date,
    reason: str,
) -> None:
    """Start a new interval, closing any currently-open one for this stock.

    The invariant "exactly one open interval per stock_id" lives here rather than in
    a constraint: a partial unique index cannot express "one NULL per group" while
    the closed intervals share the same columns.
    """
    await db.execute(
        text(
            "UPDATE symbol_history SET valid_to = :on"
            " WHERE stock_id = :sid AND valid_to IS NULL"
        ),
        {"sid": stock_id, "on": on},
    )
    await db.execute(
        text(
            "INSERT INTO symbol_history"
            " (stock_id, symbol, exchange, isin, valid_from, valid_to, reason)"
            " VALUES (:sid, :sym, :exch, :isin, :on, NULL, :reason)"
            " ON CONFLICT (symbol, exchange, valid_from) DO NOTHING"
        ),
        {
            "sid": stock_id,
            "sym": symbol,
            "exch": exchange,
            "isin": isin,
            "on": on,
            "reason": reason,
        },
    )


async def seed_from_stocks(db: Any, *, on: date) -> int:
    """Give every stock an open interval describing its CURRENT identity.

    Idempotent, and deliberately not a migration: backfilling `symbol_history` is a
    data question (what date do you claim for rows whose real first sight is
    unrecorded?), and answering it in a schema migration would bury the assumption.
    The answer taken here is `stocks.created_at::date` — honest, because for this
    database that IS the day every row was minted (2026-09-07).
    """
    result = await db.execute(
        text(
            "INSERT INTO symbol_history"
            " (stock_id, symbol, exchange, isin, valid_from, valid_to, reason)"
            " SELECT s.id, s.symbol, s.exchange, s.isin,"
            "        COALESCE(s.created_at::date, :on), NULL, :reason"
            " FROM stocks s"
            " WHERE NOT EXISTS ("
            "   SELECT 1 FROM symbol_history h WHERE h.stock_id = s.id)"
            " ON CONFLICT (symbol, exchange, valid_from) DO NOTHING"
            " RETURNING id"
        ),
        {"on": on, "reason": REASON_SEED},
    )
    return len(result.fetchall())


async def record_rename(
    db: Any,
    *,
    stock_id: int,
    new_symbol: str,
    exchange: str,
    isin: str | None,
    on: date,
) -> None:
    """A rename is applied in place on `stocks`; this is what makes it visible."""
    await open_interval(
        db,
        stock_id=stock_id,
        symbol=new_symbol,
        exchange=exchange,
        isin=isin,
        on=on,
        reason=REASON_RENAME,
    )


async def detect_isin_conflicts(
    db: Any, incoming: dict[str, str | None]
) -> list[tuple[str, str, str]]:
    """Symbols whose stored ISIN differs from the feed's. `(symbol, stored, incoming)`.

    Each one is a company merge waiting to happen, and the caller must NOT resolve it
    by writing either value.
    """
    if not incoming:
        return []
    rows = (
        await db.execute(
            text(
                "SELECT symbol, isin FROM stocks"
                " WHERE symbol = ANY(:syms) AND isin IS NOT NULL AND exchange = 'NSE'"
            ),
            {"syms": sorted(incoming)},
        )
    ).fetchall()
    out: list[tuple[str, str, str]] = []
    for r in rows:
        incoming_isin = incoming.get(str(r.symbol))
        if classify_isin_change(str(r.isin), incoming_isin) == REASON_REUSE:
            out.append((str(r.symbol), str(r.isin), str(incoming_isin)))
    return sorted(out)
