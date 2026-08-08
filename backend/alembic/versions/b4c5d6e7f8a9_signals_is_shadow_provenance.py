"""Durable shadow provenance on signals, separate from status.

`status` is a LIFECYCLE field: the expiry sweeper overwrites it with 'expired'
and the supersede policy with 'superseded'. Using it as the shadow marker meant
provenance was destroyed at exactly the moment an outcome finalised — so every
scored shadow signal became indistinguishable from a tradeable one, and a
statistic filtering on `status <> 'shadow'` would still have counted the entire
finalised history while excluding only the handful still live.

`strategy_profiles.status` is not a substitute: it is mutable, so activating a
profile later would retroactively relabel its whole shadow history as tradeable
evidence — corrupting precisely the record the shadow layer exists to build.

`is_shadow` is written once at mint and never rewritten.

Backfill: existing rows with status='shadow' are the live shadow signals from
the first shadow run; anything already swept to 'expired' predates the shadow
layer entirely (it shipped in the previous commit), so false is correct for it.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column(
            "is_shadow",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute("UPDATE signals SET is_shadow = true WHERE status = 'shadow'")
    # Partial index: every tradeable-statistics query filters `is_shadow IS FALSE`
    # over a table that is overwhelmingly non-shadow, so index the rare side.
    op.create_index(
        "idx_signals_shadow",
        "signals",
        ["created_at"],
        postgresql_where=sa.text("is_shadow"),
    )


def downgrade() -> None:
    op.drop_index("idx_signals_shadow", table_name="signals")
    op.drop_column("signals", "is_shadow")
