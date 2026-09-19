"""item 22 — gate_config_versions: the tradability configuration, versioned

⛔ Measured before writing this (M80, re-confirmed 2026-09-19): of 57 tables the only one
matching %config%/%setting%/%gate%/%version% was `alembic_version`, and `signals` carried no
column referencing a config, gate or mode. No signal could be attributed to the configuration
that produced it — while two gates had already been promoted and reverted.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gate_config_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # ⭐ UNIQUE is what makes recording idempotent: every generation run offers its
        # configuration and only a genuinely new one is stored, so the table is the history
        # of CHANGES rather than a log of runs.
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("code_commit", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_hash", name="uq_gate_config_versions_hash"),
    )
    op.create_index(
        "ix_gate_config_versions_recorded_at", "gate_config_versions", ["recorded_at"]
    )


def downgrade() -> None:
    # ⚠ Drops the configuration history. Reversible in the schema sense; the RECORD is not
    # recoverable, because nothing else in the system observes `.env`.
    op.drop_index("ix_gate_config_versions_recorded_at", table_name="gate_config_versions")
    op.drop_table("gate_config_versions")
