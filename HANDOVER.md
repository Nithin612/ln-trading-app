# HANDOVER — autonomous overnight run, 2026-09-06 → 09-07

**Branch:** `feature/pre-cycle2-hardening`
**Worktree:** `/home/nithin/code/agent/Claude/trading-platform/.claude/worktrees/pre-cycle2-hardening`

## Standing instruction (user, 2026-09-06 ~23:55 IST)

> *"start from 7.0 and proceed whatever in queue which you do not need my assistance… I am
> going to sleep now and we will meet in the morning… do not waste time"*

**Work autonomously through the queue in ID order. Commit each completed slice. DO NOT push.**

## Do NOT touch — blocked on user decisions D1–D5

| task | decision needed |
|---|---|
| #7 R1 VWAP/RVOL | **D1** frozen-engine sign-off |
| #9 R2 spread-width gate | **D2** build-or-drop (*recommend drop*) |
| #10 MCE 5b | **D3** market-cap vendor |
| #13 `compute_levels` | **D5** fix vs tourniquet |
| #15 concentration/sizing | **D4** cap enough? |

## What to read first

1. `docs/phases/pre-cycle2-queue.md` — the queue, entry check, and the five decisions
2. `docs/phases/phase-07-live-trading-plan.md` — §2 cycle-2 criteria, §3 slice split, §4 heat cap
3. `TaskList` — live status

## Ground rules that bite here

- **`make check` green is the baseline.** Last verified 2026-09-06: **1995 passed, 1 skipped,
  44 deselected, 0 failed** (`-m "not walkforward and not parity and not replay"`, 31:49).
- **Run ONE long task at a time** (pytest / agents / make check) — concurrent runs collide on
  the shared test DB's per-test truncation and surface as a phantom failure elsewhere.
- **The frozen engine is off-limits**: `app/analysis/`, `app/backtest/engine.py`, the swing/window
  canon. Bugfix-only, and any fix regenerates the Rust oracle fixtures in the same commit.
- **Doc-sync ritual runs at the END of every task**, not just at gates (CLAUDE.md).
- **Push, merge and branch creation are the user's** (W4).

## State at handover

Buckets A (8 items) and B (11 items) COMPLETE and artifact-verified; Bucket C 7 of ~60.
Queue committed at `7b1a2e1`. Nothing on the money path has changed.
