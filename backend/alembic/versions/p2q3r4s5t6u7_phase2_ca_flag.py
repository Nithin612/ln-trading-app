"""phase2_ca_flag — corporate-action quarantine marker on stocks.

Raw NSE bhavcopy history is NOT split/bonus-adjusted. Until an adjusted
source is adopted (post-Phase-3, when Kite history can serve as the
canonical adjusted series), stocks showing an unexplained price
discontinuity are QUARANTINED from suggestions rather than silently
mis-scored (reject-don't-clamp, applied to data quality).

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-07-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p2q3r4s5t6u7"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("ca_flagged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "stocks",
        sa.Column("ca_flag_reason", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stocks", "ca_flag_reason")
    op.drop_column("stocks", "ca_flagged_at")
