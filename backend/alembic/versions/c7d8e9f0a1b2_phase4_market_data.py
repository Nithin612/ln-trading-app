"""phase4_market_data

Revision ID: c7d8e9f0a1b2
Revises: 82edead41ea9
Create Date: 2026-05-18 23:30:00.000000

Creates:
  - ohlcv_1d: daily OHLCV hypertable (TimescaleDB, partitioned by time)
  - fii_dii_daily: institutional flow aggregates
  - bulk_block_deals: per-stock block/bulk deal filings
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "82edead41ea9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ohlcv_1d ─────────────────────────────────────────────────────────────
    op.create_table(
        "ohlcv_1d",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "is_complete", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("time", "stock_id"),
    )
    op.create_index("idx_ohlcv1d_stock_time", "ohlcv_1d", ["stock_id", sa.text("time DESC")])

    # Convert to TimescaleDB hypertable when the extension is available.
    # On plain PostgreSQL (CI / test DB without TimescaleDB) this is skipped silently;
    # the table still works correctly, just without time-partitioning.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN "
            "    PERFORM create_hypertable('ohlcv_1d', 'time',"
            "      chunk_time_interval => INTERVAL '1 year',"
            "      if_not_exists => TRUE); "
            "  END IF; "
            "END $$"
        )
    )

    # ── fii_dii_daily ─────────────────────────────────────────────────────────
    op.create_table(
        "fii_dii_daily",
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("investor_type", sa.String(8), nullable=False),
        sa.Column("segment", sa.String(16), nullable=False),
        sa.Column("buy_value_cr", sa.Numeric(14, 2), nullable=False),
        sa.Column("sell_value_cr", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("trade_date", "investor_type", "segment"),
    )
    op.create_index("idx_fii_dii_date", "fii_dii_daily", [sa.text("trade_date DESC")])

    # ── bulk_block_deals ──────────────────────────────────────────────────────
    op.create_table(
        "bulk_block_deals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("deal_type", sa.String(8), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("transaction", sa.String(8), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trade_date", "stock_id", "deal_type", "client_name",
            "transaction", "quantity", "price", "source",
            name="uq_bulk_block_deal",
        ),
    )
    op.create_index(
        "idx_deals_stock_date", "bulk_block_deals", ["stock_id", sa.text("trade_date DESC")]
    )


def downgrade() -> None:
    op.drop_index("idx_deals_stock_date", table_name="bulk_block_deals")
    op.drop_table("bulk_block_deals")

    op.drop_index("idx_fii_dii_date", table_name="fii_dii_daily")
    op.drop_table("fii_dii_daily")

    op.drop_index("idx_ohlcv1d_stock_time", table_name="ohlcv_1d")
    op.drop_table("ohlcv_1d")
