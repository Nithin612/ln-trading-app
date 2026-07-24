"""phase3_offmarket_entry_flag — per-user paper off-market-entry toggle.

Adds `users.allow_offmarket_entry` (default False = guard ON): paper orders
are rejected unless a live tick price exists, unless the user opts out.
Server-default false so existing rows get the safe (guard-on) value.

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-07-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u7v8w9x0y1z2"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "allow_offmarket_entry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "allow_offmarket_entry")
