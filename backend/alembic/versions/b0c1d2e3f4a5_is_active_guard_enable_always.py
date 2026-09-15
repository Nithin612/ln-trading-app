"""Close the one bypass of the `stocks.is_active` single-writer guard (§77).

⭐ **Measured, not assumed** (`scripts/universe_writer_probe.py`, 2026-09-14). The queued
question was "does an Alembic migration bypass the trigger?" and the answer is **no** — a
plain `UPDATE` is refused, so the guard covers migrations too, and §49's invariant is
stronger than the narrower "single-writer among application code" §76 settled for.

⛔ **But the probe found a bypass the question did not ask about:** the trigger was created
`ENABLE`d, which in Postgres means `tgenabled = 'O'` — *origin only* — so
`SET LOCAL session_replication_role = 'replica'` disables it wholesale. The connecting role
is a superuser, so that is reachable. `ENABLE ALWAYS` makes the trigger fire under the
replica role as well.

⚠ **Why this does not endanger a restore.** `make backup-verify` performs a REAL restore, and
`pg_restore --disable-triggers` works by setting exactly that replica role. It is safe here
because this trigger is `BEFORE UPDATE` only: a restore INSERTs (COPY), and no INSERT path is
affected. Verified against the trigger definition in `e7f8a9b0c1d2`.

⚠ **No legitimate capability is lost.** `SET LOCAL app.universe_writer = 'on'` remains the
sanctioned override and is named in the exception message itself, so a deliberate out-of-band
repair is still one line — it just can no longer happen silently.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE stocks ENABLE ALWAYS TRIGGER trg_stocks_is_active_guard")


def downgrade() -> None:
    # Back to origin-only, the state `e7f8a9b0c1d2` created it in.
    op.execute("ALTER TABLE stocks ENABLE TRIGGER trg_stocks_is_active_guard")
