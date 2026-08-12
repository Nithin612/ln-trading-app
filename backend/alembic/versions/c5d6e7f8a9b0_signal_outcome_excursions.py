"""Signal-level excursion (MFE/MAE) on signal_outcomes — Phase 6 slice 6.1.

Adds tape-derived max-favourable / max-adverse excursion (price + timing + an R
multiple), plus a computed-at marker for the idempotent backfill, to each
outcome row. All nullable — NULL means "not yet computed" (the marker
distinguishes that from "computed, no tape"). Pure observability; never feeds
scoring, sizing, gating, or backtests.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signal_outcomes", sa.Column("mfe_price", sa.Numeric(12, 4), nullable=True))
    op.add_column("signal_outcomes", sa.Column("mfe_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("signal_outcomes", sa.Column("mfe_r", sa.Numeric(7, 3), nullable=True))
    op.add_column("signal_outcomes", sa.Column("mae_price", sa.Numeric(12, 4), nullable=True))
    op.add_column("signal_outcomes", sa.Column("mae_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("signal_outcomes", sa.Column("mae_r", sa.Numeric(7, 3), nullable=True))
    op.add_column(
        "signal_outcomes",
        sa.Column("excursion_computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for col in (
        "excursion_computed_at",
        "mae_r",
        "mae_at",
        "mae_price",
        "mfe_r",
        "mfe_at",
        "mfe_price",
    ):
        op.drop_column("signal_outcomes", col)
