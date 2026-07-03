"""phase5_signals

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-05-19 00:00:00.000000

Creates:
  - sr_levels: support/resistance lines and demand/supply zones
  - signals: core output of the confluence engine
  - signal_outcomes: EOD reconciliation results
  - strategy_runs: backtest run records (Phase 9 schema, created here)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sr_levels ─────────────────────────────────────────────────────────────
    op.create_table(
        "sr_levels",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("level_type", sa.String(16), nullable=False),
        sa.Column("price_lower", sa.Numeric(12, 4), nullable=False),
        sa.Column("price_upper", sa.Numeric(12, 4), nullable=False),
        sa.Column("strength", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_touched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_touched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_broken", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("broken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sr_stock_tf", "sr_levels", ["stock_id", "timeframe", "is_broken"])

    # ── signals ───────────────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("classification", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("stop_loss", sa.Numeric(12, 4), nullable=False),
        sa.Column("take_profit", sa.Numeric(12, 4), nullable=False),
        sa.Column("suggested_qty", sa.Integer(), nullable=False),
        sa.Column("confidence_pct", sa.Integer(), nullable=False),
        sa.Column("factor_scores", postgresql.JSONB(), nullable=False),
        sa.Column("triggering_patterns", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("triggering_indicators", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("validity_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_pnl_pct", sa.Numeric(7, 3), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_signals_stock_status", "signals", ["stock_id", "status"])
    op.create_index(
        "idx_signals_active",
        "signals",
        ["validity_until"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("idx_signals_created", "signals", ["created_at"])
    op.create_index("idx_signals_class", "signals", ["classification", "created_at"])

    # ── signal_outcomes ───────────────────────────────────────────────────────
    op.create_table(
        "signal_outcomes",
        sa.Column("signal_id", postgresql.UUID(as_uuid=False), nullable=False),
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

    # ── strategy_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "strategy_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("factor_weights", postgresql.JSONB(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("universe", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("avg_rr", sa.Numeric(5, 2), nullable=True),
        sa.Column("sharpe", sa.Numeric(6, 3), nullable=True),
        sa.Column("sortino", sa.Numeric(6, 3), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("avg_holding_days", sa.Numeric(6, 2), nullable=True),
        sa.Column("ranking", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_strategy_period", "strategy_runs", ["period_start", "period_end"])


def downgrade() -> None:
    op.drop_index("idx_strategy_period", table_name="strategy_runs")
    op.drop_table("strategy_runs")
    op.drop_table("signal_outcomes")
    op.drop_index("idx_signals_class", table_name="signals")
    op.drop_index("idx_signals_created", table_name="signals")
    op.drop_index("idx_signals_active", table_name="signals")
    op.drop_index("idx_signals_stock_status", table_name="signals")
    op.drop_table("signals")
    op.drop_index("idx_sr_stock_tf", table_name="sr_levels")
    op.drop_table("sr_levels")
