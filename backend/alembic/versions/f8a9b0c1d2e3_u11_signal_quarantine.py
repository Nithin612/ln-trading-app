"""U11 — withdraw a signal without deleting it.

⛔ **The 35 signals this exists for.** They were minted 2026-09-09 → 09-11, while the
universe was broken: the scanner saw 1,322 names and **every blue chip was excluded**, so
RELIANCE and TCS could not compete for a slot. Each signal's arithmetic is fine — those
stocks had bars and the scorer ran correctly — but **the candidate SET was wrong, so they
won the wrong tournament.** All 35 are still inside their validity window (09-16 → 10-26),
so they remain live and clickable on a repaired universe that would never have produced
them.

⚠ **Not deleted, deliberately.** They are the forensic record of what the broken system
actually emitted; deleting them destroys the evidence of the failure. And ⚠ **not expressed
through `status` either** — `signals.status` is a LIFECYCLE field the sweeper overwrites
(CLAUDE.md), so a verdict parked there is a verdict that can be silently undone, and
"expired by time" would become indistinguishable from "withdrawn as contaminated".

⭐ Mirrors the `stocks.ca_flagged_at` / `ca_flag_reason` idiom already in this schema: a
nullable timestamp plus a human-readable reason, owned by nothing else.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("signals", sa.Column("quarantine_reason", sa.String(255), nullable=True))
    # The order path filters on this for every signal it is asked to trade, and the list
    # endpoint stamps it on every row it returns.
    op.create_index(
        "ix_signals_quarantined_at",
        "signals",
        ["quarantined_at"],
        postgresql_where=sa.text("quarantined_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_signals_quarantined_at", table_name="signals")
    op.drop_column("signals", "quarantine_reason")
    op.drop_column("signals", "quarantined_at")
