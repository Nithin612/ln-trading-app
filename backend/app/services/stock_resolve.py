"""V4 / A2 + A7 — search answers ABSENCE.

⭐ **The principle this exists for (§45/S2): an absence is not askable.** Everywhere else
in the app, a name the universe rule excluded simply is not there, and the user has no
way to ask why — the UI can only show what it has. **Search is the one surface where the
user names a specific stock**, so it is the one place absence CAN be answered, and it is
the cheapest place to answer it.

⚠ **Measured 2026-09-15: 1,104 of 3,395 stocks are invisible to search today** — the list
endpoint defaults `is_active=True`, so a third of the master returns nothing at all, with
no distinction between "no such company" and "excluded, and here is why".

⭐⭐ **There are TWO independent exclusions and they have different remedies**, which is the
main reason a single "not found" was so unhelpful:

  `is_active = false`        — the universe rule did not admit it. Not tradeable at all.
  `ca_flagged_at IS NOT NULL` — the CA detector quarantined it. **Measured: 5 of the 7
                               quarantined names are ACTIVE**, so they look perfectly
                               tradeable in search while `resolve_universe` silently drops
                               them from every suggestion. That gap is invisible from any
                               other surface.

⚠ **A7 — old-symbol resolution.** A rename keeps the row id (so bars, signals and
positions survive) but a user typing the OLD ticker gets nothing. `symbol_history`'s
closed intervals answer that. ⛔ Measured today: **0 renames, 0 closed intervals** — the
table was seeded with one open interval per stock and no rename has happened since. So
this half is correct and currently inert, which is stated here rather than discovered
later.

⛔ **Reasons degrade honestly (A24).** The rule's per-term reason needs the inputs that
produced the verdict, and `universe_rule_inputs` is empty until the beat next runs the
§73 code. So an exclusion always reports THAT it is excluded, and names the failing rule
term only when the recorded inputs can justify it. It never guesses.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock, SymbolHistory
from app.services.signal_service import MIN_CANDLES_TO_SCORE
from app.services.universe_materialiser import load_recorded_inputs
from app.services.universe_rule import REASON_OK, evaluate

log = logging.getLogger(__name__)

#: Human text per rule term. The rule returns a machine token; this is the only place it
#: becomes a sentence, so the wording cannot drift between surfaces.
RULE_REASON_TEXT: dict[str, str] = {
    "not_eq_listed": "not listed in the EQ series on NSE",
    "not_kite_tradable": "no tradable NSE equity instrument at the broker",
}


@dataclass(frozen=True)
class ResolvedStock:
    stock_id: int
    symbol: str
    company_name: str
    #: Admitted by the universe rule — i.e. scannable and orderable at all.
    in_universe: bool
    #: Quarantined by the CA detector. ⚠ INDEPENDENT of `in_universe`: a quarantined name
    #: can be perfectly tradeable and still absent from every suggestion.
    ca_quarantined: bool
    #: Why it is absent, in plain sentences. Empty when it is absent from nothing.
    exclusion_reasons: tuple[str, ...] = ()
    #: Former tickers this row used to trade under, newest first (A7).
    former_symbols: tuple[str, ...] = ()
    #: The date the universe verdict's reason was derived from, so a reason is never
    #: presented as timeless. None = the rule term could not be justified from a record.
    reason_as_of: date | None = None

    @property
    def suggestible(self) -> bool:
        """What `universe_service.resolve_universe` actually requires — BOTH conditions.
        Search is the only surface that can explain the difference."""
        return self.in_universe and not self.ca_quarantined


@dataclass(frozen=True)
class DataCoverage:
    """V5 — whether the scan can even LOOK at this name.

    ⭐ The per-stock form of the funnel's `admitted_to_scoring` rung, and it answers a
    question nothing else can: *why does this stock never produce a signal?*
    `signal_service` refuses any name with fewer than `MIN_CANDLES_TO_SCORE` completed
    daily candles **before scoring**, so a thin name is not rejected by the confluence
    gate — it is never examined at all. Measured by V1 on 2026-09-14: **184 of 2,286
    priced names die here, unseen**, and the whole drop was being attributed to the gate.
    """

    daily_bars: int
    min_bars_to_score: int
    latest_bar: date | None

    @property
    def enough_history(self) -> bool:
        return self.daily_bars >= self.min_bars_to_score

    @property
    def shortfall(self) -> int:
        return max(0, self.min_bars_to_score - self.daily_bars)


async def load_coverage(db: AsyncSession, stock_id: int) -> DataCoverage:
    """One stock's bar count and newest session. ⚠ Deliberately NOT called per row on a
    list — a count per row is N queries for a question a list is not asking."""
    row = (
        await db.execute(
            text(
                "SELECT count(*) AS n, max((time AT TIME ZONE 'UTC')::date) AS latest"
                " FROM ohlcv_1d WHERE stock_id = :sid"
            ),
            {"sid": stock_id},
        )
    ).one()
    return DataCoverage(
        daily_bars=int(row.n or 0),
        min_bars_to_score=MIN_CANDLES_TO_SCORE,
        latest_bar=row.latest,
    )


@dataclass
class SearchResolution:
    query: str
    hits: list[ResolvedStock] = field(default_factory=list)
    #: Set when the query matched a FORMER ticker rather than a current one.
    matched_former_symbol: str | None = None


async def _former_symbols(db: AsyncSession, stock_ids: list[int]) -> dict[int, list[str]]:
    """Closed intervals per stock — the tickers it no longer trades under."""
    if not stock_ids:
        return {}
    rows = (
        await db.execute(
            select(SymbolHistory.stock_id, SymbolHistory.symbol)
            .where(
                SymbolHistory.stock_id.in_(stock_ids),
                SymbolHistory.valid_to.is_not(None),
            )
            .order_by(SymbolHistory.valid_to.desc())
        )
    ).all()
    out: dict[int, list[str]] = {}
    for sid, sym in rows:
        out.setdefault(int(sid), []).append(str(sym))
    return out


async def _rule_reason(db: AsyncSession, symbol: str) -> tuple[str | None, date | None]:
    """The failing rule term for `symbol`, justified from the RECORDED inputs of the most
    recent evaluation — never from a fresh network fetch, and never guessed.

    ⛔ Returns `(None, None)` when no inputs are on record, which is the state until the
    materialiser beat next runs the §73 code. The caller then reports the exclusion
    without a term rather than inventing one (A24)."""
    today = date.today()
    for back in range(0, 8):  # the last few days; the beat is weekday-only
        as_of = date.fromordinal(today.toordinal() - back)
        inputs = await load_recorded_inputs(db, as_of=as_of)
        if inputs is None:
            continue
        ok, reason = evaluate(symbol, inputs)
        if ok or reason == REASON_OK:
            return None, as_of
        return RULE_REASON_TEXT.get(reason, reason), as_of
    return None, None


async def resolve_one(
    db: AsyncSession, stock: Stock, *, former_symbols: Sequence[str] = ()
) -> ResolvedStock:
    """One stock's eligibility verdict — the SINGLE implementation behind both V4's search
    and V5's stock-detail panel, so the two surfaces cannot disagree about why a name is
    unusable (W2)."""
    reasons: list[str] = []
    as_of: date | None = None
    if not stock.is_active:
        rule_text, as_of = await _rule_reason(db, stock.symbol)
        reasons.append(
            f"Not in the tradeable universe — {rule_text}."
            if rule_text
            else "Not in the tradeable universe."
        )
    if stock.ca_flagged_at is not None:
        # ⚠ Named separately and always, even for an already-excluded name: the two have
        # different remedies (re-admit vs review the price history), and a reader shown
        # only the first would chase the wrong one.
        reasons.append(
            "Quarantined by the corporate-action detector, so it is excluded from "
            "suggestions even when tradeable — review it under CA Quarantine."
        )
    return ResolvedStock(
        stock_id=stock.id,
        symbol=stock.symbol,
        company_name=stock.company_name,
        in_universe=bool(stock.is_active),
        ca_quarantined=stock.ca_flagged_at is not None,
        exclusion_reasons=tuple(reasons),
        former_symbols=tuple(former_symbols),
        reason_as_of=as_of,
    )


async def resolve_search(
    db: AsyncSession, query: str, *, stocks: list[Stock]
) -> SearchResolution:
    """Annotate search hits with WHY each one is (or is not) usable.

    `stocks` are the rows an unfiltered relevance search already found, so this adds
    meaning without running a second search — the ranking stays owned by
    `stock_service.list_stocks` (W2)."""
    res = SearchResolution(query=query.strip())
    formers = await _former_symbols(db, [s.id for s in stocks])
    for s in stocks:
        res.hits.append(await resolve_one(db, s, former_symbols=formers.get(s.id, ())))

    # Usable names first; the rest stay VISIBLE with their reason rather than vanishing.
    res.hits.sort(key=lambda h: (not h.suggestible, h.symbol))

    upper = res.query.upper()
    for hit in res.hits:
        if upper and upper in hit.former_symbols:
            res.matched_former_symbol = upper
            break
    return res


async def resolve_former_symbol(db: AsyncSession, query: str) -> Stock | None:
    """A7 — the stock that USED to trade under `query`, if any.

    A rename keeps the row id (so bars, signals and positions survive) and the old ticker
    then matches nothing, which is a dead end for a user who only knows the old name.

    ⛔ Inert today by measurement: `symbol_history` holds 3,395 rows and **zero closed
    intervals**, because it was seeded with one open interval per stock and no rename has
    occurred since. Correct and waiting, not broken."""
    upper = query.strip().upper()
    if not upper:
        return None
    sid = (
        await db.execute(
            select(SymbolHistory.stock_id)
            .where(
                SymbolHistory.symbol == upper,
                SymbolHistory.valid_to.is_not(None),
            )
            .order_by(SymbolHistory.valid_to.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sid is None:
        return None
    return (await db.execute(select(Stock).where(Stock.id == int(sid)))).scalar_one_or_none()
