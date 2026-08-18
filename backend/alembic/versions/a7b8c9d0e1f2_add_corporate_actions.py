"""add_corporate_actions — Phase 6.8.5 CA-adjust of OPEN paper positions.

Purely ADDITIVE: two new tables. `corporate_actions` holds a verified split/bonus
(ratio + ex-date); `position_corporate_actions` is the idempotency ledger (UNIQUE
per position+action) that records each R-preserving adjustment. Does NOT touch the
`positions` schema, the confluence engine, or the live path. Reversible (drop both).

Revision ID: a7b8c9d0e1f2
Revises: f4a5b6c7d8e9
Create Date: 2026-08-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "a7b8c9d0e1f2"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=16), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("ratio_from", sa.Integer(), nullable=False),
        sa.Column("ratio_to", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "stock_id", "ex_date", "action_type", name="uq_corporate_action_event"
        ),
    )
    # The ex-date worker queries CAs by ex_date; index it.
    op.create_index("idx_corporate_actions_ex_date", "corporate_actions", ["ex_date"])

    op.create_table(
        "position_corporate_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("position_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("corporate_action_id", sa.BigInteger(), nullable=False),
        sa.Column("factor", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("old_quantity", sa.Integer(), nullable=False),
        sa.Column("new_quantity", sa.Integer(), nullable=False),
        sa.Column("old_avg_entry_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("new_avg_entry_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["corporate_action_id"], ["corporate_actions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "position_id", "corporate_action_id", name="uq_position_corporate_action"
        ),
    )


def downgrade() -> None:
    op.drop_table("position_corporate_actions")
    op.drop_index("idx_corporate_actions_ex_date", table_name="corporate_actions")
    op.drop_table("corporate_actions")
