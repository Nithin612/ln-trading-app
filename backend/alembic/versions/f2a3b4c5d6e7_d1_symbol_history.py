"""D1′ — symbol_history: make identity churn visible instead of silent.

⛔ **Two kinds of identity churn exist, and only one of them was handled.**

`seed_stocks.plan_renames` already covers **ISIN keeps, symbol changes** — NSE renames
a ticker, the row is renamed IN PLACE so it keeps its id and with it every bar, signal
and position (AMIRCHAND → AEROPLANE). Correct, and it leaves **no trace**: afterwards
nothing in the database records that the old ticker ever existed, so "what was this id
called in July?" is unanswerable — which is half of why §20/2's reversal SQL is
dangerous.

The inverse — **symbol keeps, ISIN changes** — is NSE reusing a delisted ticker for a
different company. That falls through to the upsert's
`isin = COALESCE(EXCLUDED.isin, stocks.isin)`, which **overwrites the ISIN and merges
two companies into one row**: the new company inherits the dead one's id and its entire
price history, silently and irreversibly.

⚠ **Its frequency cannot be measured retrospectively** — the merge overwrites its own
evidence, so "0 mismatches today" proves nothing (our master was built FROM the same
CSV). That is why this migration records the churn rather than restructuring around it:
**`uq_stocks_symbol_exchange` is deliberately NOT dropped** (14 queries assume one row
per symbol, and a schema change that large needs a measured reason, not a plausible one).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbol_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "stock_id",
            sa.BigInteger(),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False),
        # The identity anchor AS IT WAS at the time, not as it is now: if a row's
        # ISIN is later overwritten, this is the only record of what it used to be.
        sa.Column("isin", sa.String(16), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        # NULL = current. Exactly one open interval per stock_id is the invariant;
        # it is enforced by the writer, not by a constraint, because a partial
        # unique index cannot express "one NULL per group" alongside the history.
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_symbol_history_stock_id", "symbol_history", ["stock_id"])
    op.create_index("ix_symbol_history_symbol", "symbol_history", ["symbol", "exchange"])
    # A given ticker can only START once on a given day. This is what makes symbol
    # REUSE expressible — two companies may hold the same symbol at different
    # times, which `stocks` itself cannot represent while its unique constraint
    # stands.
    op.create_unique_constraint(
        "uq_symbol_history_symbol_from",
        "symbol_history",
        ["symbol", "exchange", "valid_from"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_symbol_history_symbol_from", "symbol_history", type_="unique")
    op.drop_index("ix_symbol_history_symbol", table_name="symbol_history")
    op.drop_index("ix_symbol_history_stock_id", table_name="symbol_history")
    op.drop_table("symbol_history")
