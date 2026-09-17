"""U8 — register the sector and size indices (the registry held 3 of 166).

**WHY.** `indices` held **3 rows** — NIFTY50, BANKNIFTY, FINNIFTY — so `benchmark.py`
could only ever return NIFTY50 and every sector-RS comparison was against the broad
market, which is not a sector comparison at all. The overlay has been unevaluable since
it was built, and that is why it was never testable rather than never tested.

⭐ **The cost is one registry row each, and no code.** `index_ohlcv_service` is already
registry-driven — it maps the CSV's "Index Name" to `indices.name` and captures whatever
is registered — so the plan's step 2 ("widen the ingester") was already true when written.
The NSE indices bhavcopy the VIX recorder downloads daily carries **166 indices in one
free, no-auth file**, measured 2026-09-16.

⚠ **Every name here was verified against that live file**, not transcribed from the plan:
all 27 matched exactly. `Nifty Healthcare Index` in particular carries the trailing word
that the plan's prose ("Healthcare") omits, and a near-miss would have registered an index
that silently never ingests.

⛔ **G-Sec, bond, futures and strategy indices are deliberately NOT registered** although
they sit in the same file — ~139 of the 166. A sector-RS overlay comparing an equity
against `Nifty 10 yr Benchmark G-Sec` or `Nifty 50 Futures TR Index` is a category error,
and registering them would also multiply the daily ingest for data nothing reads.

⚠ **Registration captures GOING-FORWARD days only.** The EOD catch-up marks a date
"present" if ANY index has a row for it, so these new names need an explicit backfill
(`scripts/backfill_indices.py`) — which is a data step, not a migration's job.

⛔ **DATA ONLY — NOT a licence to flip anything.** §9/4 is explicit and two gates promoted
on arguments were refuted within weeks: `sector_rs_gate_mode` and `market_regime_gate_mode`
stay `shadow`. Data availability is not evidence.

Revision ID: c3d4e5f6a7b8
Revises: f9e8d7c6b5a4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "f9e8d7c6b5a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (symbol, exact CSV "Index Name"). The NAME is the join key the ingester matches on;
#: the symbol is ours. Verified against the live file on 2026-09-16.
_SECTOR: tuple[tuple[str, str], ...] = (
    ("NIFTYAUTO", "Nifty Auto"),
    ("NIFTYENERGY", "Nifty Energy"),
    ("NIFTYFMCG", "Nifty FMCG"),
    ("NIFTYIT", "Nifty IT"),
    ("NIFTYMEDIA", "Nifty Media"),
    ("NIFTYMETAL", "Nifty Metal"),
    ("NIFTYPHARMA", "Nifty Pharma"),
    ("NIFTYPSUBANK", "Nifty PSU Bank"),
    ("NIFTYPVTBANK", "Nifty Private Bank"),
    ("NIFTYREALTY", "Nifty Realty"),
    # ⚠ "Index" is part of the real name — the plan's prose says "Healthcare".
    ("NIFTYHEALTH", "Nifty Healthcare Index"),
    ("NIFTYOILGAS", "Nifty Oil & Gas"),
    ("NIFTYCONSDUR", "Nifty Consumer Durables"),
    ("NIFTYCOMMOD", "Nifty Commodities"),
    ("NIFTYINFRA", "Nifty Infrastructure"),
    ("NIFTYSERV", "Nifty Services Sector"),
)

#: The size ladder — the denominators a relative-strength question actually wants.
_SIZE: tuple[tuple[str, str], ...] = (
    ("NIFTYNEXT50", "Nifty Next 50"),
    ("NIFTY100", "Nifty 100"),
    ("NIFTY200", "Nifty 200"),
    ("NIFTY500", "Nifty 500"),
    ("NIFTYMIDCAP150", "Nifty Midcap 150"),
    ("NIFTYSMLCAP250", "Nifty Smallcap 250"),
    ("NIFTYMICRO250", "Nifty Microcap 250"),
    ("NIFTYTOTALMKT", "Nifty Total Market"),
)


def upgrade() -> None:
    # ⚠ ON CONFLICT on `symbol` (its unique constraint): re-running must not duplicate,
    # and NIFTY50/BANKNIFTY/FINNIFTY are already present from the original seed.
    stmt = sa.text(
        "INSERT INTO indices (symbol, name, exchange, is_active)"
        " VALUES (:symbol, :name, 'NSE', true)"
        " ON CONFLICT (symbol) DO NOTHING"
    )
    for symbol, name in _SECTOR + _SIZE:
        op.execute(stmt.bindparams(symbol=symbol, name=name))


def downgrade() -> None:
    # Bars cascade from `indices` (index_ohlcv_1d.index_id ON DELETE CASCADE), so this
    # discards their history too — correct for a reversal, and worth knowing before
    # running it after a backfill.
    symbols = tuple(s for s, _ in _SECTOR + _SIZE)
    op.execute(
        sa.text("DELETE FROM indices WHERE symbol IN :symbols").bindparams(
            sa.bindparam("symbols", value=symbols, expanding=True)
        )
    )
