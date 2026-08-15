"""add_pair_signals — the Phase-6.5b market-neutral SHADOW layer.

Purely ADDITIVE: a new `pair_signals` table for 2-leg market-neutral pair signals
(spread mean-reversion). It does NOT touch the single-name `signals` table, the
confluence engine, the paper broker, or the live order path — the running worker and
paper trading are entirely insulated. Shadow-only (`is_shadow` default true): measured
to outcome, never tradeable. Reversible (drop table). Both screening arms (df/adf) mint
here so the forward spread P&L resolves the df-vs-adf A/B.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pair_signals",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("stock_a_id", sa.BigInteger(), nullable=False),
        sa.Column("stock_b_id", sa.BigInteger(), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("half_life", sa.Float(), nullable=False),
        sa.Column("df_tstat", sa.Float(), nullable=False),
        sa.Column("adf_pvalue", sa.Float(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("entry_z", sa.Float(), nullable=False),
        sa.Column("z_exit", sa.Float(), nullable=False),
        sa.Column("z_stop", sa.Float(), nullable=False),
        sa.Column("spread_entry", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("spread_sigma", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("is_shadow", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("validity_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_z", sa.Float(), nullable=True),
        sa.Column("spread_exit", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("outcome_r", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.ForeignKeyConstraint(["stock_a_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_b_id"], ["stocks.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_pair_signals_status", "pair_signals", ["status"])
    op.create_index(
        "idx_pair_signals_method_created", "pair_signals", ["method", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_pair_signals_method_created", table_name="pair_signals")
    op.drop_index("idx_pair_signals_status", table_name="pair_signals")
    op.drop_table("pair_signals")
