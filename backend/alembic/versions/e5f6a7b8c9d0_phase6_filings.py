"""phase6_filings

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-05-19 00:00:00.000000

Creates:
  - corporate_filings: NSE/BSE corporate announcements feed
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_filings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("filing_type", sa.String(32), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("filing_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_filings_stock_time", "corporate_filings", ["stock_id", "filing_time"])
    op.create_index("idx_filings_time", "corporate_filings", ["filing_time"])
    op.create_index("idx_filings_type", "corporate_filings", ["filing_type", "filing_time"])


def downgrade() -> None:
    op.drop_index("idx_filings_type", table_name="corporate_filings")
    op.drop_index("idx_filings_time", table_name="corporate_filings")
    op.drop_index("idx_filings_stock_time", table_name="corporate_filings")
    op.drop_table("corporate_filings")
