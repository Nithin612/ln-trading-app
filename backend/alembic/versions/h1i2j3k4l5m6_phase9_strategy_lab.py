"""phase9_strategy_lab

Revision ID: h1i2j3k4l5m6
Revises: g8h9i0j1k2l3
Create Date: 2026-05-21 00:00:00.000000

Extends strategy_runs (created in Phase 5) with the columns needed to fully
store backtest results: metrics, equity curve, trade records, run metadata.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h1i2j3k4l5m6"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategy_runs", sa.Column("win_rate_pct", sa.Numeric(6, 2), nullable=True))
    op.add_column("strategy_runs", sa.Column("total_pnl_pct", sa.Numeric(10, 3), nullable=True))
    op.add_column("strategy_runs", sa.Column("avg_pnl_pct", sa.Numeric(8, 3), nullable=True))
    op.add_column("strategy_runs", sa.Column("losing_trades", sa.Integer(), nullable=True))
    op.add_column("strategy_runs", sa.Column("equity_curve", postgresql.JSONB(), nullable=True))
    op.add_column("strategy_runs", sa.Column("trades_json", postgresql.JSONB(), nullable=True))
    op.add_column(
        "strategy_runs",
        sa.Column("status", sa.String(16), nullable=False, server_default="done"),
    )
    op.add_column("strategy_runs", sa.Column("capital", sa.Numeric(14, 2), nullable=True))
    op.add_column("strategy_runs", sa.Column("risk_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("strategy_runs", sa.Column("min_confidence", sa.Integer(), nullable=True))


def downgrade() -> None:
    for col in [
        "min_confidence", "risk_pct", "capital", "status",
        "trades_json", "equity_curve", "losing_trades",
        "avg_pnl_pct", "total_pnl_pct", "win_rate_pct",
    ]:
        op.drop_column("strategy_runs", col)
