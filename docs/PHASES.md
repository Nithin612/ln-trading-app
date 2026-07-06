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
  8b-step-1 metrics ordering canon `57450f2` · 8b walk-forward runner +
  5 goldens + §8 harness (`make walkforward` in check; pins
  since=2023-07-03 / eval 2024-10-01→2026-06-30, 7 quarterly folds —
  eval_start moved from the sketched 2024-07-01: only 245 pre-context bars
  there vs the 300-bar window canon). **Walk-forward evidence: rrbo_basic
  & rrbo_trailing +41.3% / sharpe +1.97 / win 50% (58 trades) — positive;
  dc1 −52.2%, dc2 −39.7%, multibagger −1491% → flagged needs-tuning.**

NEXT — slice 9: /phase-gate (all suites + quant-verifier + bug-hunter on
the pipeline/tasks diffs + test-guardian; phase-02 report incl. per-profile
walk-forward verdicts above + the slice-7 gap that pipeline.py does not yet
feed profile.weight_multipliers into scoring (all seeds carry {} — wire
before any multiplier-carrying profile activates); flip the Phase-2 row;
PERFORMANCE.md already has canon note + walk-forward wall-clocks).

TRACK T (UNBLOCKED 2026-07-06 — user bought Kite Connect, creds in .env):
user does first login via KiteConnectPage (runbook given in-session) →
scripts/backfill_intraday.py (5m/15m, shared throttled client ~3 rps,
60-day chunks, idempotent upserts, session-completeness QA manifest;
stocks above gap threshold EXCLUDED not patched) → slice 8c (intraday
parity fixtures via scripts/generate_engine_fixtures.py, relax the off-1d
dispatch guard for pinned timeframes, intraday goldens). Phase gate may
pass on 8b with 8c trailing (approved plan). Also pending: `git push`
(user pushes manually; remote is credential-free by design).

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
