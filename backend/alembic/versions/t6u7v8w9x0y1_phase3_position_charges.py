"""phase3_position_charges — round-trip trading costs on paper positions.

Adds `positions.charges` (total Zerodha cash-equity charges for the
open→close round trip, app/trading/fees.py). `realized_pnl` becomes NET of
this from here on; gross is recoverable as realized_pnl + charges. Nullable
so the pre-cost history (closed before this migration) stays untouched.

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t6u7v8w9x0y1"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "positions",
        sa.Column("charges", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("positions", "charges")
