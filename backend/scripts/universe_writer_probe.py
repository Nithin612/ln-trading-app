"""§77 — does an Alembic migration bypass the `stocks.is_active` single-writer trigger?

Read-only on OUTCOME: every write below is rolled back. Re-runnable, because the answer is
a property of the live database's grants and trigger state, not of our source.

⭐ **Measured 2026-09-14, and the answer is not the binary the question assumed:**

  1. a plain `UPDATE` — what a naive migration does — is **REFUSED**. So an Alembic
     migration does NOT bypass the guard, and §49's invariant is stronger than the
     "single-writer among application code" it was downgraded to in §76.
  2. the materialiser's `SET LOCAL app.universe_writer = 'on'` path is allowed, so the
     one legitimate writer still writes.
  3. ⛔ but `SET LOCAL session_replication_role = 'replica'` disables it **wholesale**,
     and the connecting role IS a superuser — so the bypass exists, it is just not one
     anybody reaches by accident.

  The cause of (3) is `tgenabled = 'O'` (origin). `ENABLE ALWAYS` closes it, which is what
  migration `b0c1d2e3f4a5` does; re-run this to confirm (3) flips to REFUSED.

Usage:  cd backend && uv run python scripts/universe_writer_probe.py
"""

import asyncio

from app.db.session import AsyncSessionFactory
from sqlalchemy import text


async def main():
    async with AsyncSessionFactory() as db:
        sym = (await db.execute(text("SELECT symbol FROM stocks WHERE is_active LIMIT 1"))).scalar()
        print(f"probe target: {sym}\n")

        # 1. A plain UPDATE, the way any application code or a naive migration would.
        try:
            await db.execute(
                text("UPDATE stocks SET is_active = NOT is_active WHERE symbol = :s"), {"s": sym}
            )
            print("1. plain UPDATE            : ⛔ ALLOWED — the trigger did NOT fire")
        except Exception as e:
            print(f"1. plain UPDATE            : ✅ REFUSED — {type(e).__name__}")
        await db.rollback()

        # 2. The same UPDATE inside a transaction that identifies itself, as the
        #    materialiser does. Must be allowed, or the single writer cannot write.
        try:
            await db.execute(text("SET LOCAL app.universe_writer = 'on'"))
            await db.execute(
                text("UPDATE stocks SET is_active = NOT is_active WHERE symbol = :s"), {"s": sym}
            )
            print("2. UPDATE + universe_writer: ✅ ALLOWED (the single writer works)")
        except Exception as e:
            print(f"2. UPDATE + universe_writer: ⛔ REFUSED — {type(e).__name__}: {e}")
        await db.rollback()

        # 3. session_replication_role='replica' — the ONE documented way to silence
        #    triggers. Alembic does not set it, but a hand-run migration could.
        try:
            await db.execute(text("SET LOCAL session_replication_role = 'replica'"))
            await db.execute(
                text("UPDATE stocks SET is_active = NOT is_active WHERE symbol = :s"), {"s": sym}
            )
            print("3. UPDATE as 'replica'     : ⛔ ALLOWED — triggers disabled wholesale")
        except Exception as e:
            print(f"3. UPDATE as 'replica'     : ✅ REFUSED — {type(e).__name__}")
        await db.rollback()

        # 4. Is the connecting role a superuser (a superuser can set #3 at all)?
        su = (
            await db.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
        ).scalar()
        print(f"\nconnecting role superuser? {su}")
        enabled = (
            await db.execute(
                text("SELECT tgenabled FROM pg_trigger WHERE tgname = 'trg_stocks_is_active_guard'")
            )
        ).scalar()
        print(f"trigger tgenabled flag    : {enabled!r}  (O=origin only, A=always, D=disabled)")


asyncio.run(main())
