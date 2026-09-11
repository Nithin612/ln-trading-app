# Overnight build handoff — B-queue

**Started 2026-09-11 evening. Branch `feature/pre-cycle2-hardening`, MAIN checkout (never a worktree).**
Queue and acceptance criteria: `docs/BUILD_QUEUE.md`. Update this file after EVERY item.

## Order (round-10: money-at-risk first)

| # | item | status | commit |
|---|---|---|---|
| **B2** | `Σ notional ≤ available cash` rail | ✅ **DONE** | `e170d2b` |
| **B3** | dated tick SCHEDULE table | ✅ **DONE** | (see log) |
| **B1** | delete `_near_expiry` / `_choppy` | ⏳ IN PROGRESS | — |
| **B4** | span-based gap guard | ⏸ queued | — |
| **B5** | E1 positional in four units | ⏸ queued | — |
| **B6+B7** | E2 three estimands + MFE/MAE | ⏸ queued | — |
| **B8** | append-only ledger (ONE table, ONE day) | ⏸ queued | — |

## Standing rules for this run

- Every item ships with tests and meets its BUILD_QUEUE acceptance criteria.
- One commit per item. **Commit freely; NEVER push, never merge, never touch `main`.**
- `mypy` + targeted `pytest` per change. ⛔ **Never pass `DATABASE_URL` to pytest.**
  ⛔ Do not run full `make check` (starves under RAM pressure).
- ⛔ **Do not apply any Alembic migration to the DEV database** — write it, verify against the test
  DB, leave the dev apply for the user.
- ⛔ **Do not edit `app/analysis/`, `app/backtest/engine.py`, or `docs/SIGNAL_ENGINE.md`** — frozen /
  hook-protected.
- One long task at a time; wait for it.
- If blocked: write why here, skip, move on.

## Log

- **B2 DONE** (`e170d2b`). `cash_cap_reason` + `RULE_CASH_CAP` in `SIZING_RULES`;
  `OpenHeat.notional` from the same read; `cash_cap_mode`/`cash_cap_leverage` default **off**;
  `.env.example` documented. 9 tests inc. the acceptance criterion (3 slots at the median 5% stop
  refused at exactly 120% of capital). ruff + mypy clean, `tests/test_risk_engine.py` **50 passed**.
  ⭐ A bug was caught by its own test before shipping: the first draft netted the
  position-being-topped-up out of the held notional, but `qty` is the INCREMENT at every call
  site, so it double-discounted. Regression test built so only the aggregate rail can refuse.
  ⚠ `check_sizing` was refactored into a rail table (ruff C901 forced it) — same order, same
  stamps, same behaviour.

- **B3 DONE.** `app/broker/tick_schedule.py` — the grid as a dated price-band TABLE, each row
  carrying its own source. `paper_tick_size` default `0.05` → **`0.0` = use the schedule**;
  positive forces a flat grid. 15 tests + the acceptance criterion. **Money-path regression
  520 passed.**
  ⭐ **Measured from `ohlcv_1d`, not guessed:** sub-₹250 closes on the ₹0.05 grid ran 96–98%
  through 2020, 84–88% to 2024-05, **38.98% in 2024-06**, then 20.8–23.3% (= the 1-in-5 chance
  rate) from 2024-07. **≥₹250 never moved.** ⇒ the change took effect **June 2024**.
  ⭐⭐ **The boundary is a ZONE, not a cliff** — ₹225–250 is 39% on ₹0.05, ₹250–275 is 67%,
  ₹275–300 is 84%. The tick is a property of the INSTRUMENT (set at a review, sticky), not of
  the current price. **So the cut is at ₹225, the low end** — that can over-charge a ₹0.01 name
  but never under-charge a ₹0.05 one, which is the module contract. A ₹250 cut would have been
  wrong for ~a third of that zone.
  ⚠ **Also fixed en route:** my own round-10 PHASES edit broke the `(updated YYYY-MM-DD)` stamp
  and `tests/test_doc_sync.py` caught it. The ritual works.
