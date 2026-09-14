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
import gzip
import hashlib
import io
import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import text

from app.core.config import settings
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


async def download_equity_l() -> str:
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
        csv_text = await download_equity_l()

    kite = {
        str(r[0])
        for r in (
            await db.execute(
                text(
                    # ⚠ `segment <> 'INDICES'` is NOT redundant. Measured 2026-09-14:
                    # **212 INDICES rows carry `instrument_type = 'EQ'`**, so an index
                    # can present itself as a tradable equity. Today nothing reaches
                    # the universe that way only because the EQ_LISTED term already
                    # rejects index names — but that makes this term rely on the other
                    # one to be correct, which is how a latent defect waits. The
                    # retired `deactivate_dead_stocks.py` guarded exactly this (the
                    # "NIFTYNXT50-style ghost") and its test is preserved below.
                    "SELECT DISTINCT tradingsymbol FROM kite_instruments"
                    " WHERE instrument_type = 'EQ' AND exchange = 'NSE'"
                    "   AND segment <> 'INDICES'"
                )
            )
        ).fetchall()
    }
    return UniverseInputs(
        eq_listed=parse_eq_listed(csv_text), kite_tradable=frozenset(kite)
    )


async def record_inputs(
    db: Any, *, as_of: date, csv_text: str, inputs: UniverseInputs
) -> str:
    """Persist the rule's INPUTS for `as_of`, and commit. Returns the CSV's sha256.

    ⭐ **Call this BEFORE materialise/apply, not after.** The point of the artifact is
    that `apply_to_stocks`'s refusals become auditable, and a refusal is exactly the
    case where the later steps do not complete — recording afterwards would miss the
    only firing anyone ever needs to inspect. `universe_snapshot` stores the rule's
    OUTPUT; the collapse rail fires on a property of the INPUT, so before this table
    `universe_apply_min_fraction = 0.5` could never be tuned, because a firing could
    never be examined (§73/2).

    ⚠ Contents, not a fingerprint. A hash gives you `H(input)` while every consumer
    needs `input`, and `kite_instruments` is UPSERTED IN PLACE — so `kite_tradable` is
    unrecoverable after the fact by any route other than storing it here.

    ⚠ Idempotent per day: re-running REPLACES that date, the same contract
    `materialise()` keeps, so a re-run after a fixed input cannot leave two
    contradictory records for one date.
    """
    raw = csv_text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    await db.execute(
        text(
            "INSERT INTO universe_rule_inputs"
            " (as_of, source_url, csv_gz, csv_sha256, eq_listed, kite_tradable,"
            "  rule_version)"
            " VALUES (:d, :url, :gz, :sha, :eq, :kite, :v)"
            " ON CONFLICT (as_of) DO UPDATE SET"
            "   captured_at = now(), source_url = EXCLUDED.source_url,"
            "   csv_gz = EXCLUDED.csv_gz, csv_sha256 = EXCLUDED.csv_sha256,"
            "   eq_listed = EXCLUDED.eq_listed,"
            "   kite_tradable = EXCLUDED.kite_tradable,"
            "   rule_version = EXCLUDED.rule_version"
        ),
        {
            "d": as_of,
            "url": _EQUITY_L,
            "gz": gzip.compress(raw),
            "sha": digest,
            "eq": sorted(inputs.eq_listed),
            "kite": sorted(inputs.kite_tradable),
            "v": RULE_VERSION,
        },
    )
    await db.commit()
    log.info(
        "universe inputs %s recorded: %d EQ-listed, %d kite-tradable, csv %d B (sha %s)",
        as_of, len(inputs.eq_listed), len(inputs.kite_tradable), len(raw), digest[:12],
    )
    return digest


async def load_recorded_inputs(db: Any, *, as_of: date) -> UniverseInputs | None:
    """Rebuild a past day's `UniverseInputs` from the record — the replay half, and the
    reason the artifact is contents rather than a hash. `None` when that day was never
    captured (every day before 2026-09-14, which is most of them)."""
    row = (
        await db.execute(
            text(
                "SELECT eq_listed, kite_tradable FROM universe_rule_inputs"
                " WHERE as_of = :d"
            ),
            {"d": as_of},
        )
    ).first()
    if row is None:
        return None
    return UniverseInputs(
        eq_listed=frozenset(row.eq_listed), kite_tradable=frozenset(row.kite_tradable)
    )


async def load_recorded_csv(db: Any, *, as_of: date) -> str | None:
    """The raw source text as served that day, decompressed. Separate from
    `load_recorded_inputs` because it answers a different question: re-parsing THIS is
    what separates a source change from a parser change."""
    row = (
        await db.execute(
            text("SELECT csv_gz FROM universe_rule_inputs WHERE as_of = :d"),
            {"d": as_of},
        )
    ).first()
    return None if row is None else gzip.decompress(row.csv_gz).decode("utf-8")


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


async def apply_to_stocks(
    db: Any, *, as_of: date, min_fraction: float | None = None
) -> tuple[int, int]:
    """⭐ **The ONLY code path permitted to change `stocks.is_active` (D2′b).**

    Adopts the recorded verdict for `as_of`. Returns `(activated, deactivated)`.

    A database trigger refuses every other write — three uncoordinated writers is what
    broke the universe on 2026-09-07 — so this sets `app.universe_writer` for the
    transaction to identify itself. ⚠ `SET LOCAL` is used deliberately: the permission
    dies with the transaction, so a later statement on a pooled connection cannot
    inherit it.

    ⚠ Reads the SNAPSHOT, never the rule. `materialise()` decides and records; this
    applies what was recorded. Keeping them apart is what makes the flag's value
    explainable after the fact — the snapshot says what was decided and when, and this
    function cannot quietly decide something else.

    ⚠ Refuses an `as_of` with no snapshot rather than deactivating the entire universe.
    That is the same class of accident as the empty-dump sweep in `kite_client`.

    ⛔ **And refuses a COLLAPSE.** This runs unattended on a beat, from a rule whose
    input is a CSV fetched over the internet. A truncated or reshaped feed yields a
    small `eq_listed` set, and without this rail the nightly job would quietly switch
    off most of the market — which is precisely what the `EQ=0` header bug would have
    done on 2026-09-14 had it reached this path. Same tripwire as
    `kite_client._SWEEP_MIN_FRACTION` and the live worker's universe guard, for the
    same reason: **a feed that looks empty is a bad feed, never an empty market.**
    ⛔⛔ **AND REFUSES A SNAPSHOT THAT WOULD EXCEED THE SUBSCRIPTION CAP (round 5).**
    The collapse rail above is one-sided, and unbounded growth is not the harmless
    direction — it is the more dangerous one, because of how it COMPOSES. The U16 ceiling
    in `universe_guard` refuses the ENTIRE subscription when the universe exceeds one
    WebSocket connection's capacity, deliberately, since truncating to the first N is a
    silent selection decision. So an over-including parse regression — the exact mirror of
    the `EQ=0` header bug, which shifted a column and could as easily have admitted every
    row as none — would pass the collapse rail unchecked, push the universe past the cap,
    and the next worker start would exit `EXIT_NO_UNIVERSE`. **Every position loses its
    feed at once, including the held names U17 exists to keep subscribed.**

    ⇒ the ceiling is enforced HERE, where it is still a refused write, instead of only at
    the worker, where it is already an outage. Headroom measured 2026-09-14: 2,291 of
    3,000, so 709 names.

    ⚠ W5 — the cap is `settings.live_universe_max_count`, the same value the worker's own
    guard reads. A second copy of 3,000 here would drift from the thing it protects.
    """
    present = (
        await db.execute(
            text("SELECT count(*) FROM universe_snapshot WHERE as_of = :d"), {"d": as_of}
        )
    ).scalar_one()
    if not present:
        raise ValueError(
            f"no universe_snapshot for {as_of} — refusing to apply an empty universe. "
            "Run materialise() first."
        )

    fraction = (
        settings.universe_apply_min_fraction if min_fraction is None else min_fraction
    )
    current_active = (
        await db.execute(text("SELECT count(*) FROM stocks WHERE is_active"))
    ).scalar_one()
    if fraction and current_active and present < fraction * current_active:
        raise ValueError(
            f"universe COLLAPSE refused: the {as_of} snapshot holds {present} members "
            f"against {current_active} currently active (< {fraction:.0%}). A feed that "
            "looks empty is a bad feed, not an empty market. Investigate, then re-run "
            "with an explicit min_fraction to override."
        )

    ceiling = settings.live_universe_max_count
    if ceiling and present > ceiling:
        raise ValueError(
            f"universe CEILING refused: the {as_of} snapshot holds {present} members "
            f"against a per-connection subscription cap of {ceiling}. Applying it would "
            "make the live worker refuse its ENTIRE subscription on next start, dropping "
            "the feed for every open position. A feed that looks too large is a bad feed, "
            "not a doubled market. Investigate the parse before overriding."
        )

    await db.execute(text("SET LOCAL app.universe_writer = 'on'"))
    result = await db.execute(
        text(
            "UPDATE stocks s SET is_active = m.included, updated_at = now()"
            " FROM (SELECT s2.id,"
            "              EXISTS (SELECT 1 FROM universe_snapshot u"
            "                       WHERE u.stock_id = s2.id AND u.as_of = :d) AS included"
            "         FROM stocks s2) m"
            " WHERE m.id = s.id AND s.is_active IS DISTINCT FROM m.included"
            " RETURNING s.is_active"
        ),
        {"d": as_of},
    )
    changed = [bool(r[0]) for r in result.fetchall()]
    await db.commit()
    activated = sum(changed)
    return activated, len(changed) - activated
