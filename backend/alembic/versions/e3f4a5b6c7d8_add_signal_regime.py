"""add_signal_regime — first-class ADX regime bucket on signals (Phase 6).

Persists a committed signal's ADX trend-regime (choppy / transitional / trending /
regime n/a) at commit so the regime-eligibility overlay (app/signals/regime_guard.py)
can gate real orders off a durable field instead of re-parsing the frozen ADX
factor's prose on the money path — the documented precondition for flipping the gate
shadow→active.

Nullable + no backfill: legacy rows read NULL and the gate falls back to on-the-fly
recovery from the stored factor payload, so this is backward-compatible — old-code
workers ignore the column, only the new gate reads it (see memory: dev-migration-gap
— run `make migrate` on the DEV DB, not only the test DB).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("regime", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "regime")
