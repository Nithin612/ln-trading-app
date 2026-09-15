"""Let `universe_rule_inputs` represent "source captured, parse rejected" (§73 follow-up).

⛔ The recorder originally ran AFTER `load_inputs`, which parses — and `parse_eq_listed`
RAISES on an unrecognised header. So on the single failure this artifact exists for (the
`EQ=0` header bug: a shifted column that makes the parse return nothing), the task died
before recording anything, and the one thing that separates a SOURCE change from a PARSER
change was absent for the only day it was needed.

The fix records the bytes FIRST and fills the parsed sets in afterwards, which requires
those two columns to be nullable. NULL now means something precise and useful: **we have
exactly what the server sent, and our parser could not make sense of it.**

Revision ID: f9e8d7c6b5a4
Revises: c1d2e3f4a5b6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9e8d7c6b5a4"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "universe_rule_inputs", "eq_listed", existing_type=sa.ARRAY(sa.Text()), nullable=True
    )
    op.alter_column(
        "universe_rule_inputs", "kite_tradable", existing_type=sa.ARRAY(sa.Text()),
        nullable=True,
    )


def downgrade() -> None:
    # Any row recorded mid-parse has no sets; an empty array is the only value that can
    # satisfy NOT NULL, and it is honest — the rule saw nothing from that source.
    op.execute(
        "UPDATE universe_rule_inputs SET eq_listed = '{}' WHERE eq_listed IS NULL"
    )
    op.execute(
        "UPDATE universe_rule_inputs SET kite_tradable = '{}' WHERE kite_tradable IS NULL"
    )
    op.alter_column(
        "universe_rule_inputs", "eq_listed", existing_type=sa.ARRAY(sa.Text()), nullable=False
    )
    op.alter_column(
        "universe_rule_inputs", "kite_tradable", existing_type=sa.ARRAY(sa.Text()),
        nullable=False,
    )
