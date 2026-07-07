# Phase 2 — Strategy profiles: four style engines, offline

**Completed:** 2026-07-06 · **Exit gate:** slice 9, 2026-07-06 ·
**Plan:** `docs/UPGRADE_PLAN.md` (Phase 2) + approved slice plan
(`~/.claude/plans/fizzy-mixing-salamander.md` on the dev machine)
**Commits:** `8fa1263` (slice 0) → `7e3f9d8` (track T), 12 slice commits.
**8c (intraday parity + goldens) trails the gate by design** — approved in
the slice plan; it unblocks once the first real Kite login + backfill run.

## Goal

Turn the single confluence engine into four style engines (Intraday /
Swing / F&O / Investment) driven by versioned strategy profiles — offline,
with every ACTIVE profile carrying walk-forward evidence before any
realtime work builds on top.

## Why (what future-you needs to remember)

- **The platform had never actually measured its own edge.** v1 backtests
  existed, but no per-strategy, out-of-sample, drift-guarded evidence.
  Phase 2's real deliverable is the §8-goldened walk-forward harness — the
  numbers below are the first honest per-profile verdicts this project has
  ever produced.
- **Three "wired" things were dead until this phase**: FII/DII flows never
  reached generation (±5 factor scored 0 forever), there was NO daily
  equities-EOD ingestion task (nightly scored stale candles), and nothing
  ever expired signals (spec §5 sweeper was fiction). All three now run on
  the beat and are tested.
- **Whole-percent risk convention bites repeatedly** — slice 0 fixed the
  THIRD instance of the 100× family (`POST /signals/generate` defaulted
  `risk_pct=0.02`). Any new risk_pct entry point needs a [0.1, 10] guard.
- **Calendar-day arithmetic was quietly wrong everywhere** — swing/
  positional validity now uses real NSE trading days (46 holidays derived
  from bhavcopy session gaps: for the past, DATA is the authority, not
  published lists).

## What was built (by slice, with paths)

| Slice | Thing | Where |
|---|---|---|
| 0 | risk_pct endpoint hazard fix | `backend/app/api/v1/signals.py` |
| 1 | NSE market calendar (table + service + admin CRUD + validity wiring) | `backend/app/services/market_calendar.py`, `app/models/market_calendar.py`, `app/api/v1/calendar.py` |
| 2 | Signal expiry sweeper (5-min beat, market hours) | `backend/app/tasks/signal_tasks.py` |
| 3 | FII/DII flows → generation + beat ingestion; equities-EOD task + nightly reorder (19:15 IST) | `backend/app/services/fii_dii_service.py`, `app/tasks/` |
| 4 | Versioned `strategy_profiles` + signals linkage + typed JSONB schemas + universe service | `backend/app/models/profile.py`, `app/schemas/profile.py`, `app/services/universe_service.py` |
| 5 | Nine setup evaluators + 8 seed profiles | `backend/app/profiles/setups.py`, seed migration `o1p2q3r4s5t6` |
| 6 | Corporate-action quarantine (detector + universe exclusion; raw bhavcopy canonical) | `backend/app/services/ca_quarantine.py`* , `stocks.ca_flagged_at` |
| 7 | Suggestions pipeline + `GET /api/v1/suggestions/{style}` + nightly per-profile run (19:25 IST) | `backend/app/profiles/pipeline.py`, `app/api/v1/suggestions.py` |
| 8a | `tradecore.run_universe` + weight_multipliers/tp_rule FFI axes + factor snapshots + parity fixtures | `engine/crates/engine-py/src/lib.rs`, `backend/app/backtest/tp_rules.py` |
| 8b-1 | Metrics extraction with FIXED ordering canon (equity/maxDD compound (entry_date, stock)) | `backend/app/backtest/metrics.py` |
| 8b | Walk-forward runner + 5 goldens + §8 harness (`make walkforward` in `make check`) | `backend/app/backtest/walkforward.py`, `scripts/gen_walkforward_goldens.py`, `tests/goldens/` |
| T | Throttled Kite REST client + 5m/15m backfill + session-completeness QA manifest | `backend/app/broker/kite_rest.py`, `scripts/backfill_intraday.py` |

\* CA detector location per slice-6 commit `cac656f`.

## Results / metrics

**Walk-forward verdicts** (pins: since 2023-07-03 · eval 2024-10-01 →
2026-06-30 · 7 quarterly folds · ₹5,00,000 @ 2% whole-pct risk · goldens
under `backend/tests/goldens/walkforward/`):

| Profile | Universe (ran/excl) | Trades (pre-gate) | Win% | TotPnL% | Sharpe | MaxDD% | Verdict |
|---|---|---|---|---|---|---|---|
| rrbo_basic | NIFTY50 47/3 | 58 (427) | 50.0 | **+41.3** | **+1.97** | 40.6 | **POSITIVE** |
| rrbo_trailing† | NIFTY50 47/3 | 58 (427) | 50.0 | **+41.3** | **+1.97** | 40.6 | **POSITIVE** (approx) |
| dc1 | NIFTY50 47/3 | 289 (427) | 37.0 | −52.2 | −0.34 | 99.1 | **FLAGGED needs-tuning** |
| dc2 | NIFTY50 47/3 | 218 (427) | 36.7 | −39.7 | −0.35 | 96.8 | **FLAGGED needs-tuning** |
| multibagger | all_active 1118/1230 | 1,425 (6,341) | 21.6 | −1,491.3 | −2.07 | 100.0 | **FLAGGED needs-tuning** |

† rrbo_trailing ≡ rrbo_basic by construction this phase: `flat_pct_trailing`
approximates to `flat_pct` (no Rust trailing execution until Phase 6 tuning
/ later execution work). `multibagger` uses `ema_trail → flat 15%`. Both
approximations are pinned per golden (`tp_approximated: true`).

**Reading the table honestly:** the SR_ZONE ≥ 0.9 gate (RRBO) is the only
setup with positive out-of-sample expectancy. DC1/DC2 at ≥ 0.85 admit ~5×
more trades and lose money — the demand-zone edge exists only at the
tighter score. `multibagger` on the full market is strongly negative under
a flat-15% exit; its ema_trail semantics may fare differently once real
trailing exists (Phase 6), but AS SPECCED TODAY it must not be trusted.
TotPnL sums per-trade %; maxDD compounds sequentially under the 8b-1
ordering canon (equity curves before 2026-07-06 are not comparable).

**Suite counts at gate:** backend 607 passed · frontend
131 passed · engine (cargo) 35 passed · parity 10 · walkforward
6. `make check` green end-to-end (includes both golden harnesses).

**Wall-clocks** (docs/PERFORMANCE.md): full 5-profile walk-forward regen
≈ 24 s (multibagger 15.1 s, 1118 stocks, load-dominated); harness replay
23.3 s inside make check.

## Decisions taken

1. **eval_start = 2024-10-01, not the sketched 2024-07-01** — corpus
   starts 2023-07-03; the 300-bar window canon demands ≥300 completed bars
   before eval_start (245 vs 309 available). Symbols failing pre-context
   are EXCLUDED per golden, never patched.
2. **Goldens pin resolved symbols** — universe drift (index changes,
   CA quarantines, listings) can never silently move a golden; it shows up
   as digest/row_count drift with a [§8 APPROVAL REQUIRED] Δ-table.
3. **Golden schema is one implementation** (`build_golden` /
   `spec_from_golden` / `compare_against_existing` in walkforward.py) —
   generator and harness cannot drift on field names.
4. **TP approximations are explicit** (`tp_approximated` flag) rather than
   silently "close enough".
5. **Ordering canon for equity/maxDD** — (entry_date, stock); the old
   dict-insertion ordering made maxDD depend on universe order.
6. **CA policy**: raw bhavcopy canonical, quarantine-don't-adjust,
   quarantined stocks excluded from every universe (slice 6, before any
   golden was cut — on purpose).
7. **Test-DB serialization**: never run two pytest invocations (including
   review agents that run pytest) concurrently — the truncate-per-test
   isolation model collides across processes (40 phantom failures observed,
   clean rerun green).

## Known gaps / deferred (where they land)

- **Slice-7 gap (must fix before any multiplier profile activates):**
  `app/profiles/pipeline.py` does NOT pass `profile.weight_multipliers`
  into `score_signal` — all seeded profiles carry `{}` so live behavior is
  identical today. The walk-forward DOES honor multipliers (FFI-seam test
  pins it). Wire the pipeline in Phase 3 pre-work or the first tuning pass
  (Phase 6), whichever comes first.
- **8c — intraday parity fixtures + goldens** (trails this gate, approved):
  needs the first real Kite Connect login → `scripts/backfill_intraday.py`
  → QA manifest → extend `generate_engine_fixtures.py` for 5m/15m → relax
  the off-1d dispatch guard for pinned timeframes → intraday goldens for
  the three inactive intraday profiles.
- **dc1/dc2/multibagger tuning** → Phase 6 (weight tuning + promotion
  workflow); they stay ACTIVE for suggestion generation but their
  walk-forward verdicts are recorded as negative here.
- **Trailing-stop execution in Rust** (real `flat_pct_trailing` /
  `ema_trail` economics) → Phase 6 alongside outcome tracking.
- **fno style engine** — honest stub; suggestions API serves it empty
  until Phase 4 (F&O analytics).
- **Python engine deletion** — deferred past Phase-3 shadow week (user
  ruling, recorded in the plan).

## Gate evidence

- Frozen-file diff since freeze (`ea4b06d..HEAD` on `app/analysis/` +
  `app/backtest/engine.py`): only F/G/H adjudications (user-approved
  2026-07-05, oracles regenerated in-commit) + default-off 8a `tp_rule`
  extension + 8b aggregation extraction. Unchanged behavior proven by the
  committed fixtures passing untouched. (Independently re-derived by the
  gate quant-verifier before it was cut off: "exactly four change groups".)
- §8 drift gate demonstrated live BOTH directions: doctored golden →
  harness FAILS with Δ-table; out-of-tolerance regen → generator REFUSES
  without `--i-have-approval`. test-guardian mutation pass killed the one
  silent mutation it found (FFI kwarg seam) before commit.
- Goldens internal-consistency verified mechanically at the gate
  (win/loss/total arithmetic, fold sums vs aggregates, 7-fold set,
  tp_rule/capital/risk pins, sorted-unique symbol lists): all 5 clean.

## Gate findings fixed (bug-hunter, slice 9 — all shipped with regression tests)

1. **HIGH — Celery loop-reuse pool corruption**: every recurring DB task
   after a worker child's first died ("Future attached to a different
   loop") — sweeper/EOD-chain/nightly structurally broken in a real
   worker, invisible to the NullPool suite. Fixed via
   `app/tasks/_runner.run_db_task` (pool disposed inside each task loop),
   all 10 task bodies converted.
2. **MEDIUM — Kite retry net blind to real transport errors** (raw
   `requests` exceptions): production-confirmed when backfill run 1 died
   on an uncaught ReadTimeout ~40 min after the finding. `_TRANSIENT`
   widened; TokenException now aborts cleanly (exit 4); rate-budget clock
   updated on every attempt.
3. **MEDIUM — degenerate SL == entry crashed the whole nightly** (crash
   pair executed on real values): `app/signals/risk_guards.safe_levels`
   in both live paths + per-stock isolation in `run_profile`.
4. **MEDIUM — backfill resume-point poisoning** by consumer-minted
   forming rows: `_last_stored` now until-bounded + is_complete-filtered.
5. **LOW (backlog, latent)**: trading-day walks use UTC dates (wrong only
   for ad-hoc runs 00:00–05:30 IST; all beats safe) · `same_day` validity
   ignores weekends (no seed uses it). Fix before any same_day/eod
   profile activates or ad-hoc IST-midnight generation is added.

Review verdicts: test-guardian GAPS-FOUND → all fixed pre-commit ·
bug-hunter BUGS-FOUND (6) → 1–4 fixed at gate, 5–6 backlogged ·
quant-verifier ran twice, both cut off by account session limits — partial
evidence recorded (digest stability 200k trials clean; freeze diff = the
four sanctioned groups), full pass re-queued alongside the 8c review.

## 8c addendum (completed 2026-07-07, same day as the gate)

Delivered in four commits (`22fdaba` → `a3b1927`):

1. **session_last_bar axis** — both engines, default-off freeze-extension
   (1d oracles + all 1d goldens byte-stable); flagged decision bars mint
   nothing; open trades force-exit at flagged close after SL-before-TP.
   Rust +4 / python +8 / parity +3 tests.
2. **Intraday parity oracle** — `python_backtest_intraday_reference.json`:
   real backfilled bars (RELIANCE/TCS/HDFCBANK 15m; RELIANCE/SBIN 5m),
   session flags, **102 frozen-python trades** replayed EXACTLY by cargo
   and a dev-DB-free pytest leg. The off-1d dispatch guard is relaxed for
   pinned timeframes only (`TIMEFRAME_TABLES` whitelist).
3. **Intraday walk-forwards** (F&O 205/210 · eval 2024Q4→2026Q2 ·
   ₹5L @ 2%):

   | Profile | TF | Trades (pre-gate) | Win% | TotPnL% | Sharpe | MaxDD% | Verdict |
   |---|---|---|---|---|---|---|---|
   | pdh_pdl | 15m | 1,224 (8,684) | 40.9 | −0.3 | −1.06 | 14.8 | **FLAGGED** |
   | orb_15m | 15m | 1,045 (8,684) | 43.1 | +10.4 | −0.60 | 7.6 | **FLAGGED** (positive-sum, negative risk-adjusted) |
   | gainer_925 | 5m | 13,497 (244,440) | 41.8 | +116.3 (≈+0.009/trade) | −0.67 | 25.7 | **FLAGGED** |

   None earns Phase-3 live activation as-specced — exactly the evidence
   the phase exists to produce, now pinned in committed goldens.
4. **Two correctness catches en route:** (a) intraday loads chunk at 15
   symbols/query — a 400-symbol 5m fetch buffers >10M rows and OOM-killed
   the 16GB machine twice; (b) cross-sectional gate context (9:25 ranking
   pool) must span the PINNED ran-set, not the pre-exclusion universe —
   the mismatch drifted gainer_925 gate outcomes +3.5% between generation
   and replay, and **the §8 harness caught it on the very first replay** —
   the drift gate defending its own author.

Backfill (track T): 15.3M 5m/15m rows · 210 stocks · full 739-session
depth · QA manifest 416/420 admitted (FORCEMOT gappy, NIFTYNXT50 is an
index ticker). Plan risk #6 (Kite intraday depth) closed.
