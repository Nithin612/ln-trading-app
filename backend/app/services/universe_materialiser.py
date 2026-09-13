"""D2′a — evaluate the universe rule and record the outcome. SHADOW ONLY.

⚠ **Nothing here writes `is_active`.** This module answers *"what would the rule
say?"* and stores it. Making the rule the source of truth — removing the flag's three
writers — is D2′b, and it waits on the diff this produces, because the two gates this
project ever promoted on an argument were both refuted within weeks.

⚠ **The rule reads a live NSE CSV.** That is a network dependency inside a nightly
job, and it is the same one `seed_stocks` already carries; the alternative is storing
`series` on `stocks`, which adds a column whose freshness would then need its own
owner. The snapshot records the OUTCOME, so a later evaluation cannot silently
rewrite an earlier one.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import text

from app.services.universe_rule import (
    RULE_VERSION,
    ShadowDiff,
    UniverseInputs,
    evaluate_all,
    shadow_diff,
)

log = logging.getLogger(__name__)

_EQUITY_L = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
# The archive host expects the cookie the landing page sets; same shape as
# `vix_service.download_indices_csv`, which fetches a sibling NSE archive file.
_NSE_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


async def _download_equity_l() -> str:
    """⚠ Deliberately NOT `scripts.seed_stocks._fetch`: `app/` must not import from
    `scripts/`, and doing so also drags that module's relaxed typing in here."""
    async with httpx.AsyncClient(
        headers=_NSE_HEADERS, timeout=60, follow_redirects=True
    ) as c:
        try:
            await c.get("https://www.nseindia.com/", timeout=10)
        except httpx.HTTPError:
            pass
        resp = await c.get(_EQUITY_L)
    resp.raise_for_status()
    return resp.text


def parse_eq_listed(csv_text: str) -> frozenset[str]:
    """Symbols carrying series `EQ`. Pure, so the rule's headline input is testable
    without a network call.

    ⚠ **Header keys MUST be stripped.** `EQUITY_L.csv` ships its header as
    `SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING,…` — every column after the
    first carries a LEADING SPACE, so `row["SERIES"]` matches nothing and this
    returns an empty set rather than raising. `scripts/seed_stocks._csv_rows`
    already normalises for this and says so in a comment; the first version of this
    function did not, reported `EQ=0`, and would have "measured" that the rule
    deactivates the entire universe. A parser that returns EMPTY on a schema it does
    not recognise is the same silent-partial failure as everything else in this
    rebuild — hence the explicit guard below.
    """
    rows = [
        {k.strip(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(csv_text))
    ]
    if rows and "SERIES" not in rows[0]:
        raise ValueError(
            f"EQUITY_L has no SERIES column — got {sorted(rows[0])}. Refusing to "
            "report an empty universe from an unrecognised schema."
        )
    return frozenset(r["SYMBOL"] for r in rows if r.get("SERIES", "").upper() == "EQ")


async def load_inputs(db: Any, *, csv_text: str | None = None) -> UniverseInputs:
    """Gather the rule's inputs. `csv_text` short-circuits the download for tests."""
    if csv_text is None:
        csv_text = await _download_equity_l()

    kite = {
        str(r[0])
        for r in (
            await db.execute(
                text(
                    "SELECT DISTINCT tradingsymbol FROM kite_instruments"
                    " WHERE instrument_type = 'EQ' AND exchange = 'NSE'"
                )
            )
        ).fetchall()
    }
    return UniverseInputs(
        eq_listed=parse_eq_listed(csv_text), kite_tradable=frozenset(kite)
    )


async def _symbols(db: Any) -> dict[str, int]:
    rows = (
        await db.execute(text("SELECT symbol, id FROM stocks WHERE exchange = 'NSE'"))
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


async def materialise(db: Any, *, as_of: date, inputs: UniverseInputs) -> int:
    """Write the day's membership rows. Idempotent for a given `as_of`.

    Re-running replaces that day rather than appending, so a re-run after a fixed
    input does not leave two contradictory answers for one date.
    """
    by_symbol = await _symbols(db)
    verdicts = evaluate_all(sorted(by_symbol), inputs)
    included = [by_symbol[s] for s, (ok, _r) in verdicts.items() if ok]

    await db.execute(
        text("DELETE FROM universe_snapshot WHERE as_of = :d"), {"d": as_of}
    )
    for i in range(0, len(included), 1000):
        chunk = included[i : i + 1000]
        values = ", ".join(f"(:d, :s{j}, :v)" for j in range(len(chunk)))
        params: dict[str, Any] = {"d": as_of, "v": RULE_VERSION}
        for j, sid in enumerate(chunk):
            params[f"s{j}"] = sid
        await db.execute(
            text(
                "INSERT INTO universe_snapshot (as_of, stock_id, rule_version)"
                f" VALUES {values} ON CONFLICT (as_of, stock_id) DO NOTHING"
            ),
            params,
        )
    await db.commit()
    return len(included)


async def diff_against_live(db: Any, *, inputs: UniverseInputs) -> ShadowDiff:
    """What flipping `is_active` to the rule WOULD do. Measures, changes nothing."""
    rows = (
        await db.execute(
            text("SELECT symbol, is_active FROM stocks WHERE exchange = 'NSE'")
        )
    ).fetchall()
    live = {str(r[0]): bool(r[1]) for r in rows}
    return shadow_diff(live, evaluate_all(sorted(live), inputs))
