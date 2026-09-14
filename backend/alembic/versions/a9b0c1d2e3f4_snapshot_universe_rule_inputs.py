"""Snapshot the universe rule's INPUTS, not just its output (§73).

⭐ **Why contents and not a hash.** `docs/UNIVERSE_REBUILD_PLAN.md` §63/Q2 originally
priced this as "one CSV + one instruments hash per day". That would have built an
artifact incapable of the job: a hash gives you `H(input)` while every consumer needs
`input`. And `kite_instruments` is **upserted in place** (the sync logs "57595 rows
upserted, 0 stale swept"), so yesterday's instrument state is already gone — a hash
detects that something changed and cannot reconstruct what.

⭐⭐ **The sharpest of the four reasons is about code shipped the same week: the collapse
rail's refusals are unauditable.** `apply_to_stocks` refuses a snapshot below
`universe_apply_min_fraction`, but the rail fires on a property of the INPUT while
`universe_snapshot` records the rule's OUTPUT. So a refusal could never be reviewed and
the 0.5 threshold — picked by judgement — could never be tuned. The other three:
a rule change cannot be separated from a source change; rule v2 cannot be
regression-tested against v1; and the funnel can only call itself a detector if it can
tell a market event from an ingestion event.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universe_rule_inputs",
        # One row per evaluation date; re-running a day REPLACES it, mirroring
        # `materialise()`, so a re-run after a fixed input cannot leave two
        # contradictory answers for one date.
        sa.Column("as_of", sa.Date(), primary_key=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        # The raw bytes, gzipped. ~300 KB/day raw, ~60 KB compressed, ~250 sessions a
        # year — the ground truth a replay re-parses, so a parser change is testable
        # against what the source ACTUALLY served rather than against our reading of it.
        sa.Column("csv_gz", sa.LargeBinary(), nullable=False),
        # Cheap drift check that does not decompress: "did the source change at all".
        sa.Column("csv_sha256", sa.Text(), nullable=False),
        # The PARSED sets, stored beside the raw bytes on purpose: together they separate
        # a source change from a parser change, which is exactly what the `EQ=0` header
        # bug (a shifted column that silently returned an empty set) would have needed.
        sa.Column("eq_listed", sa.ARRAY(sa.Text()), nullable=False),
        # ⚠ `kite_instruments` is UPSERTED IN PLACE, so this set is unrecoverable after
        # the fact by any means other than recording it here.
        sa.Column("kite_tradable", sa.ARRAY(sa.Text()), nullable=False),
        # String(16), matching `universe_snapshot.rule_version` — RULE_VERSION is
        # "v1", not a number. The two tables answer the same question about the same
        # evaluation and must join on the same type.
        sa.Column("rule_version", sa.String(16), nullable=False),
    )
    # The freshness/recency questions (§77 P1) read max(as_of); the PK already orders it,
    # but captured_at answers "when was this actually fetched" for a back-filled day.
    op.create_index(
        "ix_universe_rule_inputs_captured_at", "universe_rule_inputs", ["captured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_universe_rule_inputs_captured_at", table_name="universe_rule_inputs")
    op.drop_table("universe_rule_inputs")
