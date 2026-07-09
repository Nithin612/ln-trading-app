"""phase3: rebuild ohlcv_1h session-aligned (slice 3.2)

Every pre-existing ohlcv_1h row was v1-consumer-minted on UTC-hour floors
(09:30/10:30… IST anchors, plus post-close pollution) — a different time
base from Kite's own 9:15-anchored 60minute history and from the slice-3.1
LiveEngine bucket canon. All of it is wrong; all of it is derivable.

Upgrade: delete the table body, then roll up session-aligned 1h candles
from the backfilled 5m corpus (single SQL definition shared with
app/services/ohlcv_rollup.py — the two cannot drift).

Downgrade: delete the rolled-up rows, leaving the table EMPTY. The old
UTC-floored rows are deliberately not restorable: they were garbage, and
the 5m source remains the truth to re-derive from either way.

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from app.services.ohlcv_rollup import DELETE_OHLCV_1H_SQL, REBUILD_OHLCV_1H_SQL

revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(DELETE_OHLCV_1H_SQL)
    op.execute(
        sa.text(REBUILD_OHLCV_1H_SQL).bindparams(as_of=datetime.now(tz=UTC))
    )


def downgrade() -> None:
    op.execute(DELETE_OHLCV_1H_SQL)
