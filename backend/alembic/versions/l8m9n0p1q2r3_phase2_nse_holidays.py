"""phase2_nse_holidays — market-calendar table for trading-day arithmetic.

SIGNAL_ENGINE.md §5 validity (swing 5 / positional 30 TRADING days) and
task holiday-skips require an NSE calendar; until now the code used
calendar-day approximations. Rows are seeded by
scripts/seed_nse_holidays.py (derived from bhavcopy session gaps for the
past + published NSE circular dates for the future).

Revision ID: l8m9n0p1q2r3
Revises: k7l8m9n0p1q2
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l8m9n0p1q2r3"
down_revision = "k7l8m9n0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nse_holidays",
        sa.Column("holiday_date", sa.Date(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("nse_holidays")
