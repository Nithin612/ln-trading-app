"""B8 — the append-only research/trading ledger.

⛔ **Why it exists:** `positions` and `orders` are empty. The dev database was destroyed on
2026-09-07 with no backup, and that single fact made ten rounds of live-tape argument
unfalsifiable — the offered sets, the human's choices and every realised outcome are gone and
unrecoverable. This table is the precondition for any successor programme.

⚠ **ONE table with a discriminated `node_type`, deliberately** — not the eight-table schema
the rounds proposed. One migration instead of eight, and it can be normalised later by anyone
who finds it too coarse, which is a far easier problem than resurrecting data nobody wrote.

⚠ **Append-only.** No `updated_at`. A correction is a NEW row pointing at the one it
supersedes. Reversible: the downgrade drops the table, which is safe precisely because nothing
else references it.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # ⭐ Strictly monotonic insert order. NOT `created_at`: Postgres `now()` is the
        # TRANSACTION timestamp, so rows written in one transaction share it and the chain
        # cannot be ordered by it — which a test caught immediately.
        sa.Column(
            "seq", sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1), nullable=False,
        ),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        # the causal chain
        sa.Column("chain_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        # provenance — the sample-tag rule in software
        sa.Column("code_commit", sa.String(length=40), nullable=False),
        sa.Column("spec_version", sa.String(length=32), nullable=False),
        sa.Column("experiment_id", sa.String(length=64), nullable=False),
        sa.Column("data_version", sa.String(length=64), nullable=False),
        # two time axes, and they are NOT the same axis
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq", name="uq_ledger_seq"),
    )
    op.create_index("ix_ledger_chain", "ledger_entries", ["chain_id", "seq"])
    op.create_index("ix_ledger_as_of", "ledger_entries", ["as_of", "node_type"])
    op.create_index(
        "ix_ledger_experiment", "ledger_entries", ["experiment_id", "seq"]
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_experiment", table_name="ledger_entries")
    op.drop_index("ix_ledger_as_of", table_name="ledger_entries")
    op.drop_index("ix_ledger_chain", table_name="ledger_entries")
    op.drop_table("ledger_entries")
