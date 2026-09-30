"""add cas_postclose_daily — post-close session capture (DA-7, CAS successor research).

Purely ADDITIVE: one new table, one row per (stock, trade_date), recording what the post-close
session looked like for each Category-I (F&O) stock:
  - the day's cumulative volume just AFTER the closing auction, frozen on the first poll (~15:44);
  - the peak pending buy and sell quantity seen DURING the post-close session (15:50–16:00);
  - the latest cumulative volume and last price (the last poll is ~16:04, after the session).

Why: SEBI's CAS circular (16 Jan 2026, clause 4.2.4) keeps a post-close session at the closing price,
and Zerodha accepts CNC market orders in it. So a buy at the official close is possible AFTER the
auction print is known. Whether a seller is actually there, and whether the fills we would get are
adversely selected, is unmeasured. This table is the forward record that answers it. Post-close
volume = volume_latest − volume_after_auction (valid when first_polled_at < 15:50 IST and the last
poll is after 16:00 IST).

Observability/research only. It never gates, sizes or trades, and does not touch `cas_daily`, the
confluence engine, the live path or the stocks schema. Reversible (drop the table).

Revision ID: 7c3e9a1f5b2d
Revises: d4e5f6a7b8c9
Create Date: 2026-09-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7c3e9a1f5b2d"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cas_postclose_daily",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # cumulative day volume at the FIRST poll of the post-close window (~15:44, after the
        # auction matched and before the post-close session opens at 15:50) — frozen on insert.
        sa.Column("volume_after_auction", sa.BigInteger(), nullable=True),
        # when that first poll happened; a row whose first poll is at/after 15:50 IST has a
        # baseline that already includes post-close trades, and must be excluded from volume maths.
        sa.Column(
            "first_polled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # latest cumulative volume and last price (the final poll lands after 16:00).
        sa.Column("volume_latest", sa.BigInteger(), nullable=True),
        sa.Column("last_price_latest", sa.Numeric(precision=12, scale=4), nullable=True),
        # peak pending interest seen at polls INSIDE the post-close session (15:50–16:00 IST).
        # NULL = no poll landed inside the session.
        sa.Column("max_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("max_sell_qty", sa.BigInteger(), nullable=True),
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
    op.drop_table("cas_postclose_daily")
