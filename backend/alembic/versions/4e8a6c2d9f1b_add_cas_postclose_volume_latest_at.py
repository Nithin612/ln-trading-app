"""add cas_postclose_daily.volume_latest_at — when the stored post-close volume was observed.

`volume_latest` keeps the last NON-NULL volume (COALESCE), but `captured_at` advances on every
poll, including one whose quote carried no volume. So a row can look as if it saw the whole
post-close session (last poll ≥ 16:00 IST) while its volume is from 15:52 — and a stale volume
reads as an unfilled slot. PR-2 §9a a5 needs to know when the volume itself was seen (found by
the quant-verifier on PR-1 draft v3.1, 2026-10-02).

Purely ADDITIVE and nullable. Existing rows (none yet: the first capture day is 2026-10-05) keep
NULL. Research only; reversible (drop the column).

Revision ID: 4e8a6c2d9f1b
Revises: 9b4d2f7a1c3e
Create Date: 2026-10-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4e8a6c2d9f1b"
down_revision = "9b4d2f7a1c3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cas_postclose_daily",
        sa.Column("volume_latest_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cas_postclose_daily", "volume_latest_at")
