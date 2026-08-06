"""phase3_paper_clock_start — per-user honest-fill paper-clock reset point.

Adds `users.paper_clock_started_at` (nullable). When set, the paper-record
view (and the eventual Phase-7 go-live gate) counts only closed paper trades
on/after this instant — used to restart the 30-day profitable-paper clock so
the record is measured under one honest fill model (gap-through-stop fills +
slippage). NULL = count all history (unchanged behaviour for existing rows).

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3b4c5
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "y1z2a3b4c5d6"
down_revision = "x0y1z2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("paper_clock_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "paper_clock_started_at")
