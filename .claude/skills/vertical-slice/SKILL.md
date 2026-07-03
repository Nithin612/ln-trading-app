---
name: vertical-slice
description: The standard workflow for building any feature — model → migration → service → API → frontend → tests, with the project's definition of done. Load when starting a new feature or phase deliverable.
---

# Vertical slice workflow

Every feature is built as a complete vertical slice so each merge is
demonstrable. Order is fixed; tests accompany every layer (not a final
step).

## Steps

1. **Spec check.** Find the governing docs first: SIGNAL_ENGINE.md section
   (if trading logic — spec is protected, code follows it), UPGRADE_PLAN.md
   phase item, UI_GUIDELINES.md for anything rendered. State in one sentence
   what "done" demos.
2. **Model + migration.** SQLAlchemy model (Numeric(12,4) money, TIMESTAMPTZ,
   explicit indexes for every planned WHERE/ORDER BY) → `alembic revision`
   (new file, never edit old ones) with a working `downgrade()`. Verify:
   `make migrate` then `alembic downgrade -1` then `make migrate` again.
3. **Service layer.** Pure-as-possible functions taking a session + typed
   args. Business rules live here, not in routers. Write the service tests
   NOW (real test DB, factories from tests/helpers.py).
4. **API.** Router under `app/api/v1/` with Pydantic In/Out schemas, auth
   dependency (`get_current_user` / `require_admin`), correct status codes.
   API tests: auth guard, happy path, validation 422, not-found, ownership
   isolation.
5. **Frontend.** API module in `src/lib/api/` (typed) → feature page/
   component per .claude/rules/typescript.md + ui.md → wire route + sidebar.
   Component tests: data render, skeleton, empty, error, interaction.
6. **Gate.** Run `/phase-gate` (or minimally `make check`). Update
   CHANGELOG.md under Unreleased. Manual smoke in the browser. Invoke the
   relevant reviewer agents: quant-verifier (trading logic), bug-hunter
   (pipeline/async), ui-reviewer (frontend).

## Checklists that bite

- Migration reversible? (downgrade tested, not assumed)
- Any new Redis key → TTL set? Any new contract → constant shared, both
  sides tested?
- Any new WHERE clause → index exists?
- Money Decimal end-to-end? Datetimes tz-aware? IST for market logic?
- Signals: sizing attached, validity correct, dedup respected, no
  look-ahead?
- CHANGELOG updated? Phase report (docs/phases/) updated if this closes a
  phase item?
