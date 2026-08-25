"""add cas_daily — CAS (Closing Auction Session) daily capture (Stage 1).

Purely ADDITIVE: one new table holding one row per (stock, trade_date) with the close-auction
outcome captured from Kite /quote during 3:15–3:35 IST — the pre-auction (3:15) price, the reference
price, the indicative close, the final official/auction close, and the total imbalance quantity. It is
observability/research only: it feeds the CAS overnight-reversal study (Stage 2) and NEVER gates,
sizes, or trades. Does NOT touch the confluence engine, the live path, or the stocks schema.
Reversible (drop the table).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cas_daily",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # 3:15 continuous last price, frozen on the first (pre-auction) capture of the day.
        sa.Column("pre_auction_price", sa.Numeric(precision=12, scale=4), nullable=True),
        # reference_limit_price (the 3:00–3:15 VWAP reference the exchange broadcasts).
        sa.Column("reference_price", sa.Numeric(precision=12, scale=4), nullable=True),
        # latest indicative_close_price during the auction (0 before it populates ~15:21).
        sa.Column("indicative_close", sa.Numeric(precision=12, scale=4), nullable=True),
        # latest last_price — converges to the auction clearing price after ~15:29.
        sa.Column("official_close", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("total_imbalance_qty", sa.BigInteger(), nullable=True),
        # how many polls merged into this row (audit; the window is polled every ~1 min).
        sa.Column("polls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("stock_id", "trade_date"),
    )


def downgrade() -> None:
    op.drop_table("cas_daily")
