"""phase8_paper_trading

Revision ID: g8h9i0j1k2l3
Revises: f1g2h3i4j5k6
Create Date: 2026-05-21 00:00:00.000000

Creates:
  - orders    : paper (and future live) order records
  - positions : open/closed position tracking with trail-SL state
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "g8h9i0j1k2l3"
down_revision = "f1g2h3i4j5k6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── orders ───────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("signals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stock_id",
            sa.BigInteger,
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(8), nullable=False),          # 'paper' | 'live'
        sa.Column("side", sa.String(8), nullable=False),          # 'BUY' | 'SELL'
        sa.Column("order_type", sa.String(16), nullable=False),   # 'MARKET' | 'LIMIT' | 'SL'
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=True),     # limit price
        sa.Column("trigger_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("broker_order_id", sa.String(64), nullable=True),
        sa.Column(
            "placed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("filled_qty", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("broker_payload", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_orders_user_time", "orders", ["user_id", sa.text("placed_at DESC")])
    op.create_index(
        "idx_orders_status_open",
        "orders",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'open')"),
    )

    # ── positions ─────────────────────────────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stock_id",
            sa.BigInteger,
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(8), nullable=False),          # 'paper' | 'live'
        sa.Column("side", sa.String(8), nullable=False),          # 'LONG' | 'SHORT'
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("current_sl", sa.Numeric(12, 4), nullable=True),
        sa.Column("current_tp", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "trail_state",
            sa.String(16),
            nullable=False,
            server_default="none",
        ),  # 'none' | 'breakeven' | 'trailing_1' | 'trailing_2'
        sa.Column("unrealized_pnl", sa.Numeric(14, 2), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("signals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("journal_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index(
        "idx_positions_user_open",
        "positions",
        ["user_id"],
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_index("idx_positions_user_closed", "positions", ["user_id", sa.text("closed_at DESC")])


def downgrade() -> None:
    op.drop_table("positions")
    op.drop_table("orders")
