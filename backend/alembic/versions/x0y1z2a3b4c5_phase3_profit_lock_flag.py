"""phase3_profit_lock_flag — per-user Layered Ratchet Stop toggle.

Adds `users.profit_lock_enabled` (default False = fixed trail_sl ladder):
when True, the position monitor governs open paper positions with the Layered
Ratchet Stop instead of the ladder. Server-default false so existing rows keep
the current (ladder) behaviour.

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "x0y1z2a3b4c5"
down_revision = "w9x0y1z2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "profit_lock_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "profit_lock_enabled")
