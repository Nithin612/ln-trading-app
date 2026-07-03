"""phase2_stocks_indices_screener

Revision ID: a1b2c3d4e5f6
Revises: b4945c2d75aa
Create Date: 2026-05-18 22:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b4945c2d75aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pg_trgm is already installed in the DB (confirmed during analysis).
    # We still run CREATE EXTENSION IF NOT EXISTS so the migration is safe to
    # replay on a fresh DB (e.g. CI or a new VPS).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "stocks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False),
        sa.Column("isin", sa.String(16), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(64), nullable=True),
        sa.Column("industry", sa.String(64), nullable=True),
        sa.Column("market_cap_cr", sa.Numeric(14, 2), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tick_size", sa.Numeric(8, 4), nullable=False, server_default="0.05"),
        sa.Column("is_fno", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_nifty50", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_banknifty", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_finnifty", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("listed_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),
        sa.UniqueConstraint("isin", name="uq_stocks_isin"),
    )
    op.create_index("idx_stocks_symbol", "stocks", ["symbol"])
    op.create_index("idx_stocks_sector", "stocks", ["sector"])
    op.create_index(
        "idx_stocks_fno",
        "stocks",
        ["is_fno"],
        postgresql_where=sa.text("is_active = true"),
    )
    # Trigram indexes for fuzzy symbol / company-name search
    op.create_index(
        "idx_stocks_symbol_trgm",
        "stocks",
        ["symbol"],
        postgresql_using="gin",
        postgresql_ops={"symbol": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_stocks_name_trgm",
        "stocks",
        ["company_name"],
        postgresql_using="gin",
        postgresql_ops={"company_name": "gin_trgm_ops"},
    )

    op.create_table(
        "indices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", name="uq_indices_symbol"),
    )

    op.create_table(
        "index_constituents",
        sa.Column("index_id", sa.BigInteger(), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("weight_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column(
            "added_on",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("removed_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["index_id"], ["indices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("index_id", "stock_id", "added_on"),
    )
    op.create_index(
        "idx_ic_index_active",
        "index_constituents",
        ["index_id"],
        postgresql_where=sa.text("removed_on IS NULL"),
    )

    op.create_table(
        "saved_screens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("filter_spec", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_screens_user_name"),
    )
    op.create_index("idx_saved_screens_user", "saved_screens", ["user_id"])


def downgrade() -> None:
    op.drop_table("saved_screens")
    op.drop_table("index_constituents")
    op.drop_table("indices")
    op.drop_index("idx_stocks_name_trgm", table_name="stocks")
    op.drop_index("idx_stocks_symbol_trgm", table_name="stocks")
    op.drop_index("idx_stocks_fno", table_name="stocks")
    op.drop_index("idx_stocks_sector", table_name="stocks")
    op.drop_index("idx_stocks_symbol", table_name="stocks")
    op.drop_table("stocks")
