"""phase10_journal

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2026-05-21 00:00:00.000000

Adds the journal_entries table for Phase 10 trading journal:
  - Linked to positions (auto-entries) or standalone (manual entries)
  - Full-text search index on notes + lesson columns
  - Emotion tags before/after trade
  - JSONB arrays for screenshot paths and freeform tags
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "i1j2k3l4m5n6"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stock_id",
            sa.BigInteger(),
            sa.ForeignKey("stocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(8), nullable=True),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lesson", sa.Text(), nullable=True),
        sa.Column("emotion_before", sa.String(16), nullable=True),
        sa.Column("emotion_after", sa.String(16), nullable=True),
        sa.Column(
            "screenshot_paths",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("entry_type", sa.String(8), nullable=False, server_default="manual"),
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

    op.create_index("ix_journal_entries_user_id", "journal_entries", ["user_id"])
    op.create_index("ix_journal_entries_position_id", "journal_entries", ["position_id"])
    op.create_index("ix_journal_entries_trade_date", "journal_entries", ["trade_date"])

    # Full-text search index on notes + lesson
    op.execute(
        """
        CREATE INDEX ix_journal_entries_fts
        ON journal_entries
        USING gin (
            to_tsvector('english',
                coalesce(notes, '') || ' ' || coalesce(lesson, '')
            )
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_journal_entries_fts", table_name="journal_entries")
    op.drop_index("ix_journal_entries_trade_date", table_name="journal_entries")
    op.drop_index("ix_journal_entries_position_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_user_id", table_name="journal_entries")
    op.drop_table("journal_entries")
