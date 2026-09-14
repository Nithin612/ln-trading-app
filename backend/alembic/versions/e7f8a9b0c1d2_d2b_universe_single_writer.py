"""D2′b — the universe rule becomes the source of truth for `stocks.is_active`.

⭐ **What this ends.** `is_active` was a mutable boolean with THREE writers and no
owner. On 2026-09-07 a recovery script wrote it wrong and the system spent five days
scanning 1,322 micro-caps while ignoring RELIANCE and TCS — silently, because nothing
asserted who was allowed to write it. After this migration exactly one code path may
change it: `universe_materialiser.apply_to_stocks`, from a recorded snapshot.

**Two steps, in this order for a reason.**

1. **Apply the recorded outcome.** The rule's verdict for the latest `as_of` already
   sits in `universe_snapshot`, so this is pure SQL — ⚠ **deliberately NOT a live
   evaluation.** The rule reads an NSE CSV over the network, and a migration that
   fetches from the internet is a migration that fails in a way nobody can reproduce.
   Using the recorded outcome is the whole reason D2′a recorded it.
   ⚠ Guarded: if `universe_snapshot` is empty (a fresh database) this step does
   NOTHING rather than deactivating every stock.

2. **Install the guard**, after the update, so the migration does not have to exempt
   itself from its own rule.

**The escape hatch is deliberate and discoverable:** the trigger permits a change when
the session sets `app.universe_writer = 'on'`, and the exception message says so. A
guard nobody can bypass in an emergency gets dropped in an emergency.

⚠ INSERTs are NOT blocked. A row that does not exist yet cannot have been evaluated,
so its creator must supply an initial value; `false` is the safe one (out until the
rule admits it). Only CHANGING the flag afterwards is a universe decision.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GUARD_FN = """
CREATE OR REPLACE FUNCTION stocks_is_active_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.is_active IS DISTINCT FROM OLD.is_active
       AND coalesce(current_setting('app.universe_writer', true), '') <> 'on' THEN
        RAISE EXCEPTION
            'stocks.is_active is derived from the universe rule and has ONE writer '
            '(universe_materialiser.apply_to_stocks). Direct updates are refused: '
            'three uncoordinated writers is what broke the universe on 2026-09-07. '
            'To override deliberately, run "SET LOCAL app.universe_writer = %L" in '
            'the same transaction.', 'on';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # 1. Adopt the rule's recorded verdict. No-op when no snapshot exists.
    op.execute(
        """
        UPDATE stocks s
           SET is_active = EXISTS (
                   SELECT 1 FROM universe_snapshot u
                    WHERE u.stock_id = s.id
                      AND u.as_of = (SELECT max(as_of) FROM universe_snapshot)
               ),
               updated_at = now()
         WHERE EXISTS (SELECT 1 FROM universe_snapshot)
           AND s.is_active IS DISTINCT FROM EXISTS (
                   SELECT 1 FROM universe_snapshot u
                    WHERE u.stock_id = s.id
                      AND u.as_of = (SELECT max(as_of) FROM universe_snapshot)
               )
        """
    )
    # 2. Then lock it.
    op.execute(_GUARD_FN)
    op.execute(
        "CREATE TRIGGER trg_stocks_is_active_guard BEFORE UPDATE ON stocks"
        " FOR EACH ROW EXECUTE FUNCTION stocks_is_active_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_stocks_is_active_guard ON stocks")
    op.execute("DROP FUNCTION IF EXISTS stocks_is_active_guard()")
    # The flag values are NOT reverted: they are the rule's verdict, and restoring the
    # pre-migration mixture would mean restoring a state nobody can justify.
