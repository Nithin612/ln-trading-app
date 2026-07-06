# Phase plan & status

Two eras: the **v1 build-out** (2025 → mid-2026, complete) and the **v2
upgrade** (current — approved 2026-07-03). The v2 plan's full rationale,
architecture decisions, and risks live in `docs/UPGRADE_PLAN.md`; each
completed phase writes a detailed report to `docs/phases/`.

Rule unchanged since v1: one phase at a time, vertical slices, green tests +
working demo + agent reviews before the next phase starts (`/phase-gate`).

---

## v2 upgrade phases (current)

| # | Phase | Status | Report | Key deliverable |
|---|-------|--------|--------|-----------------|
| 0 | Claude workbench · repo hygiene · triage · F&O recorders | **✅ done 2026-07-03** | [phase-00](phases/phase-00-workbench.md) | git + hooks/agents/rules/skills · 9 defects fixed (incl. dead live pipeline, 100× sizing) · F&O bhavcopy/VIX/chain recorders live |
| 1 | Rust engine core + parity + benchmarks | **✅ done 2026-07-05** (gate: `make check` green + quant-verifier signoff) | [phase-01](phases/phase-01-rust-engine.md) | tradecore wheel · 4 oracle fixtures · cross-language parity EXACT (96 windows + 125 trades) · 5 adjudicated canon decisions · **2y×49 backtest 883.8s → 0.143s (~6,180×)** |
| 2 | Strategy profiles — 4 style engines, offline | **🔶 in progress** (9 of 11 slices done, started 2026-07-05) | — | profiles table + seeds (DC1/DC2, PDH/PDL/ORB, RRBO, multibagger…), NSE holiday calendar, per-style suggestions API, walk-forward backtests |
| 3 | Realtime v2 — tick-to-tick | planned | — | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, p99 < 10 ms tick→publish. **Kite subscription required here.** Pre-shadow-week: rust-path signal envelope (patterns/indicators via FFI) + intraday parity goldens (then drop the off-1d python fallback) — see phase-01 §Exit gate |
| 4 | F&O analytics | planned | — | chain builder, Rust IV/Greeks, IV-rank/PCR/max-pain from recorded history, option-selling suggestions (calibrated with user) |
| 5 | UI overhaul | planned | — | new sidebar IA, slate theme default, 4 style pages, chain ladder, virtualized live tables @60fps |
| 6 | Outcome tracking + strategy lab v2 | planned | — | per-style hit-rate/expectancy dashboards, factor attribution, Rayon weight tuning + promotion workflow |
| 7 | Live-trading hardening | planned | — | Kite orders behind trading_mode + 30-day gate, kill switch, reconciliation, VPS runbook |

**▶ CONTINUE HERE (next session, any account — say "continue Phase 2"):**
Phase 2 is mid-flight; the approved slice plan is mirrored below (full
detail: `~/.claude/plans/fizzy-mixing-salamander.md` on the dev machine).
Baseline discipline unchanged: every slice ships tests + CHANGELOG, lint/
mypy green, frozen files only via sanctioned extensions.

DONE (each its own commit, all green):
- 0 risk_pct=0.02 endpoint hazard `8fa1263` · 1 NSE market calendar
  `f31c91e` · 2 expiry sweeper `0aa4566` · 3 FII/DII flows + EOD pipeline
  ordering `e142e16` · 4 strategy_profiles schema `4fb1f5d` · 5 setup
  evaluators + 8 seeds `fa5f384` · 7 suggestions pipeline +
  `GET /api/v1/suggestions/{style}` `b3a8bcf` · 8a Rust FFI run_universe +
  multiplier/tp_rule parity axes `ff67b21` · 6 CA quarantine `cac656f` ·
  8b-step-1 metrics ordering canon `57450f2`.

NEXT — finish slice 8b (walk-forward runner + 1d goldens + §8 harness):
1. `backend/app/backtest/walkforward.py`: per ACTIVE profile — resolve
   universe (pinned symbol list), load candles from a PINNED `since` with
   ≥300 bars pre-context before `eval_start`, ONE tradecore.run_universe
   call (map profile risk_template → tp_rule: rr/flat_pct direct;
   flat_pct_trailing→flat_pct; ema_trail→flat_pct(min_target) — documented
   approximations), map integer trade indices→dates per stock, apply setup
   gates as an exact python post-filter (trade dicts carry the factor
   snapshot), drop fills < eval_start, bin trades into CALENDAR-QUARTER
   folds, aggregate via app/backtest/metrics.aggregate_trades.
2. `scripts/gen_walkforward_goldens.py`: dry-run default; --write refuses
   any >5% metric move without --i-have-approval; golden JSON per active
   profile under backend/tests/goldens/walkforward/: embedded config +
   config_hash + tradecore version + since/eval_start/eval_end + pinned
   symbols + row_counts + exclusions + per-fold & aggregate metrics +
   sha256 trades_digest. Suggested pins: since=2023-07-03,
   eval_start=2024-07-01, eval_end=2026-06-30 (8 quarters).
3. Harness `tests/goldens/test_walkforward_goldens.py`
   (pytest.mark.walkforward — register the mark; skip-cleanly-on-empty-DB
   like the parity suite), `make walkforward` target wired into make
   check. Failure prints the Δ-table with [§8 APPROVAL REQUIRED] rows.
4. Then slice 9: /phase-gate (all suites + quant-verifier + bug-hunter on
   the pipeline/tasks diffs + test-guardian; phase-02 report; flip this
   row; PERFORMANCE gets backfill + walk-forward wall-clocks).

BLOCKED ON USER: track T (Kite subscription + first login via
KiteConnectPage) → then scripts/backfill_intraday.py (5m/15m, throttled,
QA manifest) → slice 8c (intraday parity fixtures via
scripts/generate_engine_fixtures.py, relax the off-1d dispatch guard for
pinned timeframes, intraday goldens). Phase gate may pass on 8b with 8c
trailing (approved plan). Also pending: `git push` (user pushes manually;
remote is credential-free by design).

Phase-1 state (closed): F/G/H applied 2026-07-05, canon table in
ARCHITECTURE.md; standing baseline 599 trades / +52.1% / sharpe +0.13 on
the pinned 2y×49 corpus.

**Decision gates (unchanged in spirit from v1):**
- End Phase 1: parity green or no cutover.
- End Phase 2: every profile shows documented expectancy (or is flagged) before realtime work.
- End Phase 3: full-session soak clean before F&O/UI build on top. 30-day paper clock starts here.
- Before Phase 7 live pilot: 30 profitable paper days with discipline, static IP, kill-switch tested.

**Zerodha API:** not needed for Phases 0–2 (NSE public data + existing DB).
Nice-to-have from Phase 2 (historical intraday backfill). **Required at
Phase 3 start.** The chain-snapshot recorder (built in Phase 0) activates
automatically once a token exists.

---

## v1 build-out (complete — kept for history)

| # | Phase | Status |
|---|-------|--------|
| 0 | Infrastructure (docker compose: Timescale+Redis) | ✅ |
| 1 | Auth & user master (JWT, rotation, admin-only creation) | ✅ |
| 2 | Stock master + 50-filter screener + saved screens | ✅ |
| 3 | Categories master (M2M tagging) | ✅ |
| 4 | EOD ingestion (5y OHLCV, FII/DII, bulk/block deals) | ✅ |
| 5 | Signal engine offline (14 factors, confluence ≥70%, backtest harness) | ✅ |
| 6 | Dashboard v1 + corporate filings feed + event guard | ✅ |
| 7 | Live data via Kite WS (unit-tested; end-to-end defects repaired in v2 Phase 0) | ✅* |
| 8 | Paper trading (positions, trail SL, circuit breaker) | ✅ |
| 9 | Strategy lab (grid search, presets, equity curves) | ✅ |
| 10 | Trading journal (auto-populate, emotions, screenshots) | ✅ |
| 11 | External portfolio (CAMS CAS import, net worth) | ✅ |
| 12 | Live trading | → became v2 Phase 7 |

\* v1 Phase 7 shipped with four integration defects that made the live path
inoperable end-to-end (documented in UPGRADE_PLAN.md and repaired, with
regression tests, in v2 Phase 0 — see `docs/phases/phase-00-workbench.md`).

## Consciously deferred (unchanged)

Mobile native app · Account Aggregator integration · AI/ML signal
generation (only after the rule-based engine proves out) · multi-tenancy /
SaaS hardening · MCX commodities. FinBERT sentiment stays deferred
(column exists, never populated).
