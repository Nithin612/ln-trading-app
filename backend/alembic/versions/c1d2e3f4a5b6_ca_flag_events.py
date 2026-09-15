"""Give the CA quarantine a clearing path, and an append-only record of both sides (§77).

**Q-R3, measured.** `stocks.ca_flagged_at` had exactly one writer (`ca_detector.py:92`)
and **no clearer anywhere** — no script, no endpoint, no admin path — while `stock.py`'s
own docstring says "unflag via admin after verifying". The quarantine was a MONOTONIC
ACCUMULATOR, and it is filling: measured 2026-09-14, **7 stocks flagged, 5 of them active,
4 of the 7 flagged that same day**. A flagged stock is excluded from every suggestion
universe (`universe_service.resolve_universe`), so the set of tradeable names shrinks by
about four a week with no way back.

⛔ **An EXPIRY was considered and rejected.** The contamination lives in the unadjusted
price history, and that does not heal with time — a split's bars stay wrong until the
series is adjusted or ages out of every indicator window. An expiry would silently
re-admit contaminated history on a timer, which is worse than a flag nobody clears.

⭐ **Why a log rather than `ca_cleared_at/_by/_reason` on `stocks`.** The detector skips
rows where `ca_flagged_at IS NULL`, so a cleared name CAN be flagged again — and the next
flag would overwrite the record of the review that released it. §41 named that trap when
it refused to drop `uq_stocks_symbol_exchange`: the merge overwrites its own evidence, and
the rate of the thing you wanted to measure becomes unmeasurable retrospectively.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ca_flag_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "stock_id",
            sa.Integer(),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(16), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        # Required on BOTH sides: the detector's gap description when flagged, the
        # reviewer's justification when cleared. "Cleared, no reason given" is not audit.
        sa.Column("reason", sa.Text(), nullable=False),
        # NULL for a machine flag; the admin on a clear. The asymmetry is the point —
        # a machine may quarantine, only a person may release.
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("event IN ('flagged', 'cleared')", name="ck_ca_flag_event"),
    )
    op.create_index("ix_ca_flag_events_stock_id", "ca_flag_events", ["stock_id"])
    # The history reads newest-first per stock, and "what was released lately" is the
    # review-queue question.
    op.create_index("ix_ca_flag_events_at", "ca_flag_events", ["at"])

    # ⭐ Backfill the flags that already exist, so the log does not start by implying the
    # 7 live quarantines arrived from nowhere. `at` is the real flag time we still have;
    # the reason is the detector's own stored text.
    op.execute(
        """
        INSERT INTO ca_flag_events (stock_id, event, at, reason, actor_user_id)
        SELECT id, 'flagged', ca_flagged_at,
               coalesce(ca_flag_reason, 'flagged before the event log existed'), NULL
          FROM stocks
         WHERE ca_flagged_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ca_flag_events_at", table_name="ca_flag_events")
    op.drop_index("ix_ca_flag_events_stock_id", table_name="ca_flag_events")
    op.drop_table("ca_flag_events")
