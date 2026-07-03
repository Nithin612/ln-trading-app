"""phase11_portfolio

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-05-21 00:00:00.000000

Adds three tables for Phase 11 External Portfolio:
  - mf_import_batches: one row per CAMS CAS PDF upload
  - mf_holdings: individual scheme holdings per batch
  - manual_assets: gold, FDs, PPF, NPS, bonds, real estate, other
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j1k2l3m4n5o6"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── mf_import_batches ─────────────────────────────────────────────────────
    op.create_table(
        "mf_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("statement_date", sa.Date(), nullable=True),
        sa.Column("investor_name", sa.String(200), nullable=True),
        sa.Column("pan", sa.String(12), nullable=True),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("total_holdings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_value",
            sa.Numeric(16, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_mf_import_batches_user_id", "mf_import_batches", ["user_id"])
    op.create_index("ix_mf_import_batches_created_at", "mf_import_batches", ["created_at"])

    # ── mf_holdings ───────────────────────────────────────────────────────────
    op.create_table(
        "mf_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("mf_import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amc_name", sa.String(200), nullable=False),
        sa.Column("scheme_name", sa.String(300), nullable=False),
        sa.Column("folio_number", sa.String(50), nullable=False),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("units", sa.Numeric(18, 4), nullable=False),
        sa.Column("nav", sa.Numeric(12, 4), nullable=False),
        sa.Column("current_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_mf_holdings_batch_id", "mf_holdings", ["batch_id"])
    op.create_index("ix_mf_holdings_user_id", "mf_holdings", ["user_id"])

    # ── manual_assets ─────────────────────────────────────────────────────────
    op.create_table(
        "manual_assets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("institution", sa.String(200), nullable=True),
        sa.Column("current_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("purchase_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("units", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_manual_assets_user_id", "manual_assets", ["user_id"])
    op.create_index("ix_manual_assets_asset_type", "manual_assets", ["asset_type"])


def downgrade() -> None:
    op.drop_index("ix_manual_assets_asset_type", table_name="manual_assets")
    op.drop_index("ix_manual_assets_user_id", table_name="manual_assets")
    op.drop_table("manual_assets")

    op.drop_index("ix_mf_holdings_user_id", table_name="mf_holdings")
    op.drop_index("ix_mf_holdings_batch_id", table_name="mf_holdings")
    op.drop_table("mf_holdings")

    op.drop_index("ix_mf_import_batches_created_at", table_name="mf_import_batches")
    op.drop_index("ix_mf_import_batches_user_id", table_name="mf_import_batches")
    op.drop_table("mf_import_batches")
