"""add index_ohlcv_1d — MCE slice 2 index price store.

Purely ADDITIVE: one new table holding daily EOD OHLC per market/sector index,
keyed on the existing `indices` registry (FK). It is the missing keystone for
relative-strength context — the tradeable engine had the index registry +
membership but no index *price* series. Fed from the NSE indices bhavcopy CSV (no
Kite dependency). Does NOT touch the confluence engine, the live path, or the
`stocks`/`indices` schema. Reversible (drop the table).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_ohlcv_1d",
        sa.Column("index_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("high", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("low", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("close", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["index_id"], ["indices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("index_id", "trade_date"),
    )


def downgrade() -> None:
    op.drop_table("index_ohlcv_1d")
