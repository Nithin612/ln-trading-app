"""phase7_live_data

Revision ID: f1g2h3i4j5k6
Revises: e5f6a7b8c9d0
Create Date: 2026-05-19 00:00:00.000000

Creates:
  - ohlcv_1m  : 1-minute candles hypertable (7-day chunks)
  - ohlcv_5m  : 5-minute candles hypertable (1-month chunks)
  - ohlcv_15m : 15-minute candles hypertable (1-month chunks)
  - ohlcv_1h  : 1-hour candles hypertable (3-month chunks)
  - broker_tokens    : per-user Kite access tokens
  - kite_instruments : symbol → instrument_token mapping from Kite CSV
"""

import sqlalchemy as sa
from alembic import op

revision = "f1g2h3i4j5k6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

_INTRADAY_TABLES = [
    ("ohlcv_1m", "7 days"),
    ("ohlcv_5m", "1 month"),
    ("ohlcv_15m", "1 month"),
    ("ohlcv_1h", "3 months"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── Intraday OHLCV tables ────────────────────────────────────────────────
    for table, _chunk in _INTRADAY_TABLES:
        op.create_table(
            table,
            sa.Column("time", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "stock_id",
                sa.BigInteger,
                sa.ForeignKey("stocks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("open", sa.Numeric(12, 4), nullable=False),
            sa.Column("high", sa.Numeric(12, 4), nullable=False),
            sa.Column("low", sa.Numeric(12, 4), nullable=False),
            sa.Column("close", sa.Numeric(12, 4), nullable=False),
            sa.Column("volume", sa.BigInteger, nullable=False),
            sa.Column("is_complete", sa.Boolean, nullable=False, server_default="false"),
            sa.PrimaryKeyConstraint("time", "stock_id"),
        )
        op.create_index(
            f"idx_{table.replace('ohlcv_', 'ohlcv')}_stock_time",
            table,
            ["stock_id", sa.text("time DESC")],
        )

        # Convert to TimescaleDB hypertable if extension is present
        result = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb' LIMIT 1"
            )
        )
        if result.fetchone():
            conn.execute(
                sa.text(
                    f"SELECT create_hypertable('{table}', 'time',"
                    f" chunk_time_interval => INTERVAL '{_chunk}',"
                    f" if_not_exists => TRUE)"
                )
            )

    # ── broker_tokens ────────────────────────────────────────────────────────
    op.create_table(
        "broker_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("broker", sa.String(32), nullable=False, server_default="kite"),
        sa.Column("access_token", sa.String(512), nullable=False),
        sa.Column("request_token", sa.String(512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_broker_tokens_user", "broker_tokens", ["user_id"])

    # ── kite_instruments ─────────────────────────────────────────────────────
    op.create_table(
        "kite_instruments",
        sa.Column("instrument_token", sa.Integer, primary_key=True),
        sa.Column("exchange_token", sa.Integer, nullable=False),
        sa.Column("tradingsymbol", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(16), nullable=False),
        sa.Column("instrument_type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("last_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("tick_size", sa.Numeric(8, 4), nullable=False, server_default="0.05"),
        sa.Column("lot_size", sa.Integer, nullable=False, server_default="1"),
        sa.Column("segment", sa.String(32), nullable=False),
        sa.Column("expiry", sa.String(16), nullable=False, server_default=""),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_kite_instr_exchange_symbol",
        "kite_instruments",
        ["exchange", "tradingsymbol"],
    )


def downgrade() -> None:
    op.drop_table("kite_instruments")
    op.drop_table("broker_tokens")
    for table, _ in reversed(_INTRADAY_TABLES):
        op.drop_table(table)
