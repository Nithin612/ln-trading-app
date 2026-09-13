"""D2′a — universe_snapshot: the universe as a dated, reproducible OUTCOME.

⭐ The universe stops being a mutable boolean anyone can write and becomes something
EVALUATED and RECORDED. This migration is additive and shadow-only: nothing reads
this table on the money path yet, and `is_active` is untouched. Flipping the source
of truth is D2′b, and it waits on a measured diff.

⚠ **Membership rows only.** Presence means included. Storing a row per EXCLUDED name
would triple the table to answer a question whose inputs we do not snapshot anyway —
the rule reads today's `EQUITY_L.csv` and today's `kite_instruments`, neither of which
is retained, so "why was Y out on date D" is not reconstructible however much we
write here. "Was X in on D" is, exactly, and that is the question backtests ask.

Revision ID: d6e7f8a9b0c1
Revises: f2a3b4c5d6e7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universe_snapshot",
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "stock_id",
            sa.BigInteger(),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Which rule admitted it. A snapshot without this cannot be compared across
        # a rule change, which is the whole point of versioning the rule.
        sa.Column("rule_version", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("as_of", "stock_id", name="pk_universe_snapshot"),
    )
    # The query this table exists to serve: "the universe as of D".
    op.create_index("ix_universe_snapshot_as_of", "universe_snapshot", ["as_of"])


def downgrade() -> None:
    op.drop_index("ix_universe_snapshot_as_of", table_name="universe_snapshot")
    op.drop_table("universe_snapshot")
