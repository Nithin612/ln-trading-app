# Phase 0 — Claude workbench, repo hygiene, triage, F&O recorders

**Completed:** 2026-07-03 · **Plan:** `docs/UPGRADE_PLAN.md` (Phase 0 section)
**Commits:** baseline `920225c` → `565f127`+ (see `git log` for the full chain)

## Goal

Make every future phase faster and safer: version control, a working
toolchain, Claude Code guardrails (hooks/agents/rules/skills), repairs for
the defects the adversarial review found in already-built code, and F&O
data recorders started early because recorded calendar time is the scarce
resource for options analytics.

## Why (what future-you needs to remember)

- The repo had **no git history** and a **dead venv** (snap refresh
  garbage-collected the interpreter) — 453 "green" tests could not even run.
- The v1 live pipeline was **never functional end-to-end** despite green
  unit tests: four independent integration defects (thread/asyncio, SQL
  builder, transaction, Redis key contract). Lesson encoded into
  `.claude/rules/testing.md`: test the seams, not just the units.
- Every system-generated signal was **sized at 1/100th** of intended risk
  (double percent division). All paper P&L before 2026-07-03 is invalid;
  the 30-day live-gate clock restarts.
- Options analytics (Phase 4) need IV/OI history that Kite does not sell —
  so the recorders had to start **now**, not in Phase 4.

## What was built

1. **Repo hygiene** — git init + pristine baseline commit; `.gitignore`
   hardened (the stock `lib/` pattern would have ignored `frontend/src/lib/`);
   venv rebuilt on durable non-snap Python 3.12.13; ruff+mypy to zero.
2. **Workbench** — `.claude/settings.json` (permissions, deny-list) ·
   hooks: `format.sh` (auto-format per language), `guard-bash.sh`
   (destructive commands; 12 verified cases), `guard-files.sh`
   (SIGNAL_ENGINE.md / applied migrations / .env; 7 verified cases) ·
   agents: quant-verifier, bug-hunter, ui-reviewer, perf-auditor,
   test-guardian (strict evidence contracts; register at session start) ·
   rules: trading-domain, python, typescript, rust, testing, ui ·
   skills: /vertical-slice, /phase-gate, /signal-audit, /perf-bench.
3. **Triage fixes** (all with regression tests): sizing 100×; the four
   tick-pipeline defects; loop survival + task supervision; candle
   timestamp astimezone + `exchange_timestamp` field; cumulative-volume
   diffing; /ws/live keepalive-anchored reader + JWT auth (4401);
   signal dedup guard; Redis volatile-lru; backtests via asyncio.to_thread;
   `asyncio.run` in all Celery tasks; connection-leak closes.
4. **F&O recorders** — `fo_bhavcopy` (UDiFF EOD, beat 18:45 IST),
   `india_vix_daily`, `option_chain_snapshots` hypertable (1-min kite.quote
   snapshots, NIFTY/BANKNIFTY, idles without token); NFO instruments synced
   with strikes; migration `k7l8m9n0p1q2` proven reversible
   (upgrade → downgrade → upgrade).
5. **Docs** — UPGRADE_PLAN.md committed; CLAUDE.md/README/PHASES rewritten
   to current truth; ARCHITECTURE.md + PERFORMANCE.md started;
   TECH_STACK_RATIONALE gains the Rust section; this report protocol begun.

## Results / metrics

| Gate | Result |
|---|---|
| Backend tests | **439 passed** (394 baseline + 45 new) |
| Frontend tests | **131 passed** (17 files) |
| Ruff | clean (was 48 findings) |
| Mypy (strict, 112 files) | clean (was 18 errors) |
| Hooks | 19/19 guard cases + formatter verified |
| Migration | reversible (up→down→up) |
| Agent validation | bug-hunter contract run on the tick-pipeline diff: 9 findings, 3 CONFIRMED with runnable reproductions — all fixed in-phase |

## Decisions taken

- **volatile-lru** over a second Redis instance (TTL-less broker keys
  become non-evictable; every cache key must carry a TTL — rule recorded).
- **Idempotency via active-signal skip**, not a DB unique constraint —
  supersede-on-stronger-signal deliberately deferred to Phase 2 design.
- Chain recorder keeps the **2N+1 strikes nearest spot** (N=10 default,
  `FO_CHAIN_UNDERLYINGS`/`FO_CHAIN_STRIKES_EACH_SIDE` in config).
- **1h candle table left UTC-anchored** for now — rebuild session-aligned
  scheduled for Phase 3 with SIGNAL_ENGINE §8 regression sign-off (known,
  documented debt in ARCHITECTURE.md).
- Backtest fill realism (gap-through-SL, same-candle SL/TP) intentionally
  NOT changed — it goes through the Phase 1 adjudication so goldens don't
  canonize accidental semantics.

## Deferred / carried forward

- Phase 1 adjudication checkpoint (user decisions): volume direction-match,
  RSI ±0.4 bands, SL canon (backtest 20-bar vs live pivot), window canon
  (last-300 vs incremental), fill realism.
- NSE holiday calendar (Phase 2) — market-hours gate currently
  weekday+time only; `expiry.py` still approximates trading days.
- Dev `.env` JWT secret is 12 bytes (pyjwt warns; fine for dev, rotate ≥32
  bytes before any non-local deployment).
- kite_instruments sync currently syncs on demand — scheduled daily
  re-sync + live-worker re-subscribe cycle arrives with Phase 3.

## How to see it working

```bash
make check                                   # full gate, all green
cd backend && uv run pytest tests/test_fo_recorders.py -q   # recorders
uv run alembic current                       # k7l8m9n0p1q2 (head)
# F&O EOD ingestion, manually for one date (needs internet, free NSE):
uv run python -c "
import asyncio, datetime as dt
from app.db.session import AsyncSessionFactory
from app.services.fo_bhavcopy_service import ingest_fo_bhavcopy_date
async def main():
    async with AsyncSessionFactory() as db:
        print(await ingest_fo_bhavcopy_date(db, dt.date(2026, 7, 2)))
asyncio.run(main())"
```
