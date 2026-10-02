"""add cas_daily.first_polled_at — the instant of the first CAS poll, frozen on insert.

`cas_daily.pre_auction_price` is the last traded price at the FIRST poll inside the auction window.
It is the last continuous trade only if that poll came before the auction could print (order entry
closes at random 15:28–15:30 IST, matching runs 15:30–15:35). Nothing recorded when that poll
happened: `captured_at` is rewritten on every poll, so it holds the LAST poll's time (found by the
quant-verifier on PR-1 draft v3.1, 2026-10-02). PR-2 §9a a1 needs this column to know a
`pre_auction_price` is valid.

Purely ADDITIVE and nullable. Existing rows keep NULL: their first-poll instant was never stored
and is not reconstructed (`polls` cannot rebuild it — duplicate beats have doubled polls before).
Mirrors `cas_postclose_daily.first_polled_at`. Research only; reversible (drop the column).

Revision ID: 9b4d2f7a1c3e
Revises: 7c3e9a1f5b2d
Create Date: 2026-10-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9b4d2f7a1c3e"
down_revision = "7c3e9a1f5b2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cas_daily",
        sa.Column("first_polled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cas_daily", "first_polled_at")
