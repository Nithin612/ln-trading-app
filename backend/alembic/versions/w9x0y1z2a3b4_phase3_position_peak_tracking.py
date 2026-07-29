"""phase3_position_peak_tracking — max favourable excursion on positions.

Adds `positions.peak_price` (best price reached while open) and
`positions.peak_pnl` (GROSS peak profit, i.e. max favourable excursion × qty).
The position monitor updates these each live tick. Together with realized_pnl
they quantify profit leakage (peak − realised) — the metric the Dynamic Profit
Lock work targets — and give the shadow comparator a live MFE independent of
candle retention. Nullable; NULL until the monitor first sees a live tick.

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-07-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "w9x0y1z2a3b4"
down_revision = "v8w9x0y1z2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "positions",
        sa.Column("peak_price", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "positions",
        sa.Column("peak_pnl", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("positions", "peak_pnl")
    op.drop_column("positions", "peak_price")
