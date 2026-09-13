"""D0 — the stock-identity pin: making `stocks.id` survive a rebuild.

⛔ **The failure this exists for.** Every `stocks.id` in this database was minted
on 2026-09-07 by an emergency reconstruction, and every one of them was REASSIGNED
in the process. `docs/UNIVERSE_REBUILD_PLAN.md` §20/2 measured the consequence: the
`deactivate_dead_stocks.py` docstring's reversal SQL, which joins on raw
`stock_id`, now reactivates the WRONG COMPANIES — July's `stock_id = 228` was
`QUINTEGRA`, today's is `BSE`.

⭐ **What pinning does and does not buy.** Restoring from a `pg_dump` carries ids
with it, so this adds nothing there. It matters in the case that actually happened:
a rebuild from SOURCE (re-seed `stocks`, re-attach bars from the bhavcopy archive).
Bars re-attach BY SYMBOL so they stay internally consistent, but every artifact
keyed on an id from before — probe JSONL dumps, forensic tables, analysis output —
silently points at a different company. **Pinning makes a source rebuild reproduce
the same mapping, so those artifacts survive it.**

⚠ **A pin file nothing reads is decoration.** The verifier is the point: it reports
CONFLICTS (a symbol whose id moved) separately from NEW and MISSING names, because
only the first is a correctness failure — the other two are ordinary listing churn.

⚠ This module is deliberately pure — no DB, no clock, no I/O — so the comparison
can be tested without a database and reused by both the export and the check.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

FIELDNAMES = ("stock_id", "symbol", "isin", "first_seen")


@dataclass(frozen=True)
class PinnedStock:
    stock_id: int
    symbol: str
    isin: str | None
    first_seen: str


@dataclass
class IdentityDiff:
    """The three outcomes, kept apart because only one of them is a defect."""

    conflicts: list[tuple[str, int, int]] = field(default_factory=list)
    """(symbol, pinned_id, live_id) — the SAME name under a DIFFERENT id. This is
    the 2026-09-07 failure, and it invalidates every id-keyed artifact."""

    missing: list[str] = field(default_factory=list)
    """Pinned names absent from the live DB — delisting, or an incomplete rebuild."""

    added: list[str] = field(default_factory=list)
    """Live names not in the pin — new listings. Expected; re-export to adopt."""

    @property
    def ok(self) -> bool:
        """Only conflicts fail. Churn is not drift."""
        return not self.conflicts


def serialise(rows: list[PinnedStock]) -> str:
    """CSV text, sorted by symbol so a re-export produces a reviewable diff rather
    than a reshuffle."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDNAMES, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda x: x.symbol):
        w.writerow(
            {
                "stock_id": r.stock_id,
                "symbol": r.symbol,
                "isin": r.isin or "",
                "first_seen": r.first_seen,
            }
        )
    return buf.getvalue()


def parse(text: str) -> list[PinnedStock]:
    out: list[PinnedStock] = []
    for row in csv.DictReader(io.StringIO(text)):
        out.append(
            PinnedStock(
                stock_id=int(row["stock_id"]),
                symbol=row["symbol"].strip(),
                isin=(row["isin"].strip() or None),
                first_seen=row["first_seen"].strip(),
            )
        )
    return out


def diff(pinned: list[PinnedStock], live: dict[str, int]) -> IdentityDiff:
    """Compare a pin against `{symbol: stock_id}` from the live database."""
    d = IdentityDiff()
    pinned_by_symbol = {p.symbol: p for p in pinned}
    for symbol, p in sorted(pinned_by_symbol.items()):
        live_id = live.get(symbol)
        if live_id is None:
            d.missing.append(symbol)
        elif live_id != p.stock_id:
            d.conflicts.append((symbol, p.stock_id, live_id))
    d.added = sorted(set(live) - set(pinned_by_symbol))
    return d
