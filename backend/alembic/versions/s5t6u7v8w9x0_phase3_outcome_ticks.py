"""phase3_outcome_ticks — signal-outcome tick evaluation (slice 3.6).

Replaces the v1 `signal_outcomes` EOD-reconciliation shape (never
written or read by any code path; verified 0 rows) with the tick-level
first-touch schema the outcome recorder writes and Phase 6 aggregates.
Fail-loud guard: refuses to drop a non-empty table.

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-07-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None


def _assert_empty() -> None:
    conn = op.get_bind()
    n = conn.execute(sa.text("SELECT count(*) FROM signal_outcomes")).scalar()
    if n:
        raise RuntimeError(
            f"signal_outcomes holds {n} rows — refusing to drop. "
            "Export/inspect before migrating (this table was believed dead)."
        )


def upgrade() -> None:
    _assert_empty()
    op.drop_table("signal_outcomes")
    op.create_table(
        "signal_outcomes",
        sa.Column("signal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("validity_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=24), nullable=False, server_default="open"
        ),
        sa.Column("entry_touched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_touch_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("sl_touched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sl_touch_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("tp_touched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tp_touch_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_id"),
    )
    op.create_index("idx_signal_outcomes_status", "signal_outcomes", ["status"])
    op.create_index(
        "idx_signal_outcomes_class_status",
        "signal_outcomes",
        ["classification", "status"],
    )


def downgrade() -> None:
    _assert_empty()
    op.drop_index("idx_signal_outcomes_class_status", table_name="signal_outcomes")
    op.drop_index("idx_signal_outcomes_status", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
    # the v1 EOD-reconciliation shape, verbatim (from d0e1f2a3b4c5)
    op.create_table(
        "signal_outcomes",
        sa.Column("signal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("hit_target", sa.Boolean(), nullable=False),
        sa.Column("hit_sl", sa.Boolean(), nullable=False),
        sa.Column("max_favorable_pct", sa.Numeric(7, 3), nullable=True),
        sa.Column("max_adverse_pct", sa.Numeric(7, 3), nullable=True),
        sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl_pct", sa.Numeric(7, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_id"),
    )
