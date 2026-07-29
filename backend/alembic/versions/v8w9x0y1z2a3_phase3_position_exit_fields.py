"""phase3_position_exit_fields — denormalised exit price + reason on positions.

Adds `positions.exit_price` (Numeric(12,4)) and `positions.exit_reason`
(sl_hit / tp_hit / manual). The data already existed on the closing Order
(`filled_price` + `broker_payload["reason"]`); denormalising it onto the
position lets Trade History render "why did this close, and at what price"
without joining orders per row. Nullable so open positions and pre-migration
closed history stay valid.

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-07-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v8w9x0y1z2a3"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "positions",
        sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "positions",
        sa.Column("exit_reason", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("positions", "exit_reason")
    op.drop_column("positions", "exit_price")
