"""add nse_special_sessions — exchange sessions held on a weekend.

The NSE calendar was `weekday AND not a holiday`, so it could not represent a session held on a
Saturday or Sunday. The archive has 8 (Union Budget days, DR drills, muhurat trading:
2019-10-27 … 2026-02-01), and every one was invisible to EOD ingest, the catch-up healer and the
scheduled tasks. This table lets `market_calendar` count them. Purely additive; reversible.

Revision ID: 5f2a8c1e7d3b
Revises: 4e8a6c2d9f1b
Create Date: 2026-10-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5f2a8c1e7d3b"
down_revision = "4e8a6c2d9f1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nse_special_sessions",
        sa.Column("session_date", sa.Date(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("open_ist", sa.Time(), nullable=True),
        sa.Column("close_ist", sa.Time(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("nse_special_sessions")
