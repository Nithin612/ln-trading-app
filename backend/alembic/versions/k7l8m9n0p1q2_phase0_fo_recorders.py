"""phase0_fo_recorders — F&O bhavcopy, India VIX, option-chain snapshots.

Also widens kite_instruments tokens to BIGINT (Kite tokens are uint32 —
int32 can overflow) and adds a strike column so NFO option instruments can
be stored by the extended instrument sync.

Revision ID: k7l8m9n0p1q2
Revises: j1k2l3m4n5o6
Create Date: 2026-07-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k7l8m9n0p1q2"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── kite_instruments: BIGINT tokens + strike for NFO rows ────────────────
    op.alter_column(
        "kite_instruments", "instrument_token",
        type_=sa.BigInteger(), existing_type=sa.Integer(), existing_nullable=False,
    )
    op.alter_column(
        "kite_instruments", "exchange_token",
        type_=sa.BigInteger(), existing_type=sa.Integer(), existing_nullable=False,
    )
    op.add_column(
        "kite_instruments",
        sa.Column("strike", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    # NFO chain lookups: underlying name + type + expiry
    op.create_index(
        "idx_kite_instr_nfo_chain",
        "kite_instruments",
        ["name", "instrument_type", "expiry"],
        postgresql_where=sa.text("exchange = 'NFO'"),
    )

    # ── fo_bhavcopy ───────────────────────────────────────────────────────────
    op.create_table(
        "fo_bhavcopy",
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("instrument", sa.String(4), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("open", sa.Numeric(12, 4), nullable=True),
        sa.Column("high", sa.Numeric(12, 4), nullable=True),
        sa.Column("low", sa.Numeric(12, 4), nullable=True),
        sa.Column("close", sa.Numeric(12, 4), nullable=True),
        sa.Column("settle_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("underlying_close", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume_contracts", sa.BigInteger(), nullable=True),
        sa.Column("open_interest", sa.BigInteger(), nullable=True),
        sa.Column("change_in_oi", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint(
            "trade_date", "symbol", "instrument", "expiry_date", "strike"
        ),
    )
    # PCR / max-pain / IV-history queries scan one symbol across dates
    op.create_index(
        "idx_fo_bhav_symbol_date",
        "fo_bhavcopy",
        ["symbol", sa.text("trade_date DESC")],
    )
    op.create_index(
        "idx_fo_bhav_expiry",
        "fo_bhavcopy",
        ["symbol", "expiry_date", "trade_date"],
    )

    # ── india_vix_daily ──────────────────────────────────────────────────────
    op.create_table(
        "india_vix_daily",
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(8, 4), nullable=True),
        sa.Column("high", sa.Numeric(8, 4), nullable=True),
        sa.Column("low", sa.Numeric(8, 4), nullable=True),
        sa.Column("close", sa.Numeric(8, 4), nullable=False),
        sa.PrimaryKeyConstraint("trade_date"),
    )

    # ── option_chain_snapshots (hypertable) ──────────────────────────────────
    op.create_table(
        "option_chain_snapshots",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_token", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("ltp", sa.Numeric(12, 4), nullable=True),
        sa.Column("bid", sa.Numeric(12, 4), nullable=True),
        sa.Column("ask", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("oi", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("time", "instrument_token"),
    )
    op.create_index(
        "idx_chain_snap_symbol_time",
        "option_chain_snapshots",
        ["symbol", "expiry_date", sa.text("time DESC")],
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN "
            "    PERFORM create_hypertable('option_chain_snapshots', 'time',"
            "      chunk_time_interval => INTERVAL '7 days',"
            "      if_not_exists => TRUE); "
            "  END IF; "
            "END $$"
        )
    )


def downgrade() -> None:
    op.drop_table("option_chain_snapshots")
    op.drop_table("india_vix_daily")
    op.drop_index("idx_fo_bhav_expiry", table_name="fo_bhavcopy")
    op.drop_index("idx_fo_bhav_symbol_date", table_name="fo_bhavcopy")
    op.drop_table("fo_bhavcopy")
    op.drop_index("idx_kite_instr_nfo_chain", table_name="kite_instruments")
    op.drop_column("kite_instruments", "strike")
    # Narrowing back can fail if >int32 tokens were stored meanwhile — that is
    # the correct failure mode for a lossy downgrade.
    op.alter_column(
        "kite_instruments", "exchange_token",
        type_=sa.Integer(), existing_type=sa.BigInteger(), existing_nullable=False,
    )
    op.alter_column(
        "kite_instruments", "instrument_token",
        type_=sa.Integer(), existing_type=sa.BigInteger(), existing_nullable=False,
    )
