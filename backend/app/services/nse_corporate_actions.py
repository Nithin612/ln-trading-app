"""Queue item 16 — corporate actions as a CACHE OF THE AUTHORITY'S ANSWERS.

⭐⭐ **The rule this implements, stated in the build queue and earned elsewhere in this
project: a predicate encoding an external authority must be a CACHE OF ITS ANSWERS, not a
RULE YOU EVALUATE.** The alternative we have been living with is a rule: flag any
`|open ÷ prev_close − 1| > 25%` and call it a corporate action. M70 measured that screen at
**62.5% false-positive** — of 8 flagged events, 3 were corporate actions and 5 were genuine
price moves (ZEEL ×2 on the Sony/Invesco news, IDEA, ADANIENT ×2). A screen that wrong cannot
decide what to drop from a study, because dropping the real moves deletes the most informative
sessions in the block.

⛔ **Why this is needed NOW, and by what:** item 5's estimand **3b** (the matched-tail contrast
— whether the ≥70% gate selects anything) is a MEAN forward-return contrast, so a single
split-induced −89.8% moves the answer by roughly `0.9/n`. 3a survived without this because it
is a Spearman RANK correlation and a split only moves a name to last place. **3b cannot run
until the CA set is real**, and the test block's liquid pool holds **225** screen candidates.

## What the authority actually publishes

`https://www.nseindia.com/api/corporates-corporateActions` — the same free `/api/` surface the
app already uses for FII/DII (D3's resolution: no vendor needed). It returns everything: AGMs,
dividends, rights, interest payments on government securities. Verified 2026-09-19 for
January 2024 — 15 records, of which 1 was a government security and only 4 were splits or
bonuses.

⚠ **The ratio is published as PROSE, not as a field.** `"Bonus 1:1"`,
`"Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share"`. So parsing is
unavoidable — which means this is a cache of answers that still needs one rule applied to read
them. The honest handling, and the design here: **store the raw subject verbatim on every row,
parse only what is unambiguous, and record what could not be parsed rather than dropping it.**
An unparsed action is a known unknown; a dropped one is a silent hole.

⛔⛔ **TWO CONVENTIONS THAT WILL PRODUCE SILENTLY WRONG ADJUSTMENTS IF CONFUSED.**

1. **NSE publishes the BONUS ratio; `CorporateAction` stores the TOTAL.** `"Bonus 3:1"` means
   *three new shares for every one held*, so a holder ends with **four**. The model's own
   docstring says a 1:1 bonus is `ratio_from=1, ratio_to=2`. Storing 3:1 verbatim would apply
   a ×3 adjustment where ×4 is correct.
2. **A face-value split is quoted in FACE VALUE, which moves the OPPOSITE way to the share
   count.** "From Rs 10 to Re 1" is a *tenth* of the face value and therefore **ten times**
   the shares.

⚠ **Rights issues and dividends are NOT stored**, because `CorporateAction.action_type` admits
only `split | bonus`. Rights are genuinely dilutive and do move the price — they are reported
in the ingest summary as `unsupported` rather than ignored, so the gap is visible.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corporate_action import CorporateAction
from app.models.stock import Stock
from app.services.fii_dii_service import _NSE_HEADERS, _prime_nse_session

log = logging.getLogger(__name__)

CA_URL = "https://www.nseindia.com/api/corporates-corporateActions"

#: Only cash-equity series. The feed also carries government securities (`GS`) and others.
EQUITY_SERIES = {"EQ", "BE"}

#: `Bonus 3:1` — three NEW shares per one held.
_BONUS = re.compile(r"\bbonus\b[^0-9]{0,12}(\d+)\s*:\s*(\d+)", re.I)

#: `Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share`
_SPLIT = re.compile(
    r"from\s+(?:rs|re)\.?\s*([0-9]+(?:\.[0-9]+)?)\s*/?-?\s*per\s+share"
    r"\s*to\s+(?:rs|re)\.?\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)


@dataclass(frozen=True)
class ParsedAction:
    """One authority record, parsed. `raw` is always kept."""

    symbol: str
    ex_date: date
    action_type: str          # split | bonus
    ratio_from: int           # shares held
    ratio_to: int             # shares after
    raw: str


def parse_subject(subject: str) -> tuple[str, int, int] | None:
    """`(action_type, ratio_from, ratio_to)` or None if this is not a split/bonus.

    Returns None — never a guess — for AGMs, dividends, rights and anything unrecognised.
    """
    if not subject:
        return None

    if (m := _BONUS.search(subject)) is not None:
        new, held = int(m.group(1)), int(m.group(2))
        if new <= 0 or held <= 0:
            return None
        # ⛔ NSE's "new per held" → the model's TOTAL: a holder of `held` ends with `held+new`.
        f = Fraction(held + new, held)
        return "bonus", f.denominator, f.numerator

    if "split" in subject.lower() and (m := _SPLIT.search(subject)) is not None:
        fv_before, fv_after = Fraction(m.group(1)), Fraction(m.group(2))
        if fv_before <= 0 or fv_after <= 0 or fv_after >= fv_before:
            return None  # not a sub-division; a consolidation or a malformed line
        # ⛔ Face value moves OPPOSITE to share count: /10 face value ⇒ ×10 shares.
        f = fv_before / fv_after
        return "split", f.denominator, f.numerator

    return None


def _parse_ex_date(value: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


async def fetch_corporate_actions(
    from_date: date, to_date: date, *, client: httpx.AsyncClient | None = None
) -> tuple[list[ParsedAction], list[dict[str, str]]]:
    """`(parsed splits/bonuses, records we could NOT parse)`.

    ⚠ The second list is the point. An action the parser does not understand is REPORTED, not
    discarded — a silent drop is indistinguishable from "there was no action", which is the
    failure mode this whole item exists to end.
    """
    owned = client is None
    c = client or httpx.AsyncClient(
        headers=_NSE_HEADERS, timeout=30, follow_redirects=True
    )
    try:
        if owned:
            await _prime_nse_session(c)
        resp = await c.get(
            CA_URL,
            params={
                "index": "equities",
                "from_date": from_date.strftime("%d-%m-%Y"),
                "to_date": to_date.strftime("%d-%m-%Y"),
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owned:
            await c.aclose()

    if not isinstance(payload, list):
        raise ValueError(f"unexpected corporate-actions payload: {type(payload).__name__}")

    parsed: list[ParsedAction] = []
    unsupported: list[dict[str, str]] = []
    for rec in payload:
        series = (rec.get("series") or "").strip().upper()
        symbol = (rec.get("symbol") or "").strip().upper()
        subject = (rec.get("subject") or "").strip()
        ex = _parse_ex_date(rec.get("exDate") or "")
        if series not in EQUITY_SERIES or not symbol or ex is None:
            continue
        got = parse_subject(subject)
        if got is None:
            unsupported.append({"symbol": symbol, "ex_date": ex.isoformat(), "subject": subject})
            continue
        action_type, rf, rt = got
        parsed.append(ParsedAction(symbol, ex, action_type, rf, rt, subject))
    return parsed, unsupported


async def ingest_corporate_actions(
    db: AsyncSession, from_date: date, to_date: date, *, client: httpx.AsyncClient | None = None
) -> dict[str, object]:
    """Upsert authority-sourced actions into `corporate_actions` (`source="nse"`).

    ⚠ **Never overwrites a `manual` row.** An admin-verified ratio was checked by a person
    against the actual event; the feed's prose parse has not been. Where both exist the human
    wins and the conflict is reported.
    """
    parsed, unsupported = await fetch_corporate_actions(from_date, to_date, client=client)

    symbols = {p.symbol for p in parsed}
    rows = (
        await db.execute(select(Stock.id, Stock.symbol).where(Stock.symbol.in_(symbols)))
    ).all() if symbols else []
    id_of = {sym: sid for sid, sym in rows}

    inserted = skipped_unknown = already = conflicts = 0
    conflict_rows: list[str] = []
    for p in parsed:
        sid = id_of.get(p.symbol)
        if sid is None:
            skipped_unknown += 1
            continue
        existing = (
            await db.execute(
                select(CorporateAction).where(
                    CorporateAction.stock_id == sid,
                    CorporateAction.ex_date == p.ex_date,
                    CorporateAction.action_type == p.action_type,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.source == "manual" and (
                existing.ratio_from != p.ratio_from or existing.ratio_to != p.ratio_to
            ):
                conflicts += 1
                conflict_rows.append(
                    f"{p.symbol} {p.ex_date} manual {existing.ratio_from}:{existing.ratio_to} "
                    f"vs nse {p.ratio_from}:{p.ratio_to}"
                )
            already += 1
            continue
        db.add(
            CorporateAction(
                stock_id=sid, action_type=p.action_type, ex_date=p.ex_date,
                ratio_from=p.ratio_from, ratio_to=p.ratio_to, source="nse", note=p.raw,
            )
        )
        inserted += 1
    await db.flush()

    return {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "parsed": len(parsed),
        "inserted": inserted,
        "already_present": already,
        "unknown_symbol": skipped_unknown,
        "unsupported": len(unsupported),
        "unsupported_sample": unsupported[:10],
        "manual_conflicts": conflicts,
        "conflict_rows": conflict_rows,
    }
