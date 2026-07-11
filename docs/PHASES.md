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
| 2 | Strategy profiles — 4 style engines, offline | **✅ done 2026-07-07** (gate: suites 616/131/35 green · smoke · reviews; 8c trails by approved plan) | [phase-02](phases/phase-02-strategy-profiles.md) | versioned profiles + 8 seeds · NSE calendar · FII/DII + EOD chain wired · suggestions API · **walk-forward evidence: rrbo +41.3%/+1.97 sharpe POSITIVE; dc1/dc2/multibagger FLAGGED** · §8 golden harness in make check · Kite login + throttled REST + intraday backfill |
| 3 | Realtime v2 — tick-to-tick | **▶ in progress** (started 2026-07-09) | [phase-03](phases/phase-03-realtime.md) | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, p99 < 10 ms tick→publish. **Kite subscription required from slice 3.3.** Slice 3.0 (pre-work MEDIUMs) ✅ 2026-07-09 |
| 4 | F&O analytics | planned | — | chain builder, Rust IV/Greeks, IV-rank/PCR/max-pain from recorded history, option-selling suggestions (calibrated with user) |
| 5 | UI overhaul | planned | — | new sidebar IA, slate theme default, 4 style pages, chain ladder, virtualized live tables @60fps |
| 6 | Outcome tracking + strategy lab v2 | planned | — | per-style hit-rate/expectancy dashboards, factor attribution, Rayon weight tuning + promotion workflow |
| 7 | Live-trading hardening | planned | — | Kite orders behind trading_mode + 30-day gate, kill switch, reconciliation, VPS runbook |

**▶ CONTINUE HERE (next session, any account):** Phase 3 IN PROGRESS —
**slices 3.0–3.5-core ALL DONE and on `main`** (3.0–3.3 on 2026-07-09,
3.4 on 2026-07-10, 3.5 core + first-soak ops + publish-path perf fixes
2026-07-10/11; ledger + all review records: `phases/phase-03-realtime.md`;
CHANGELOG Unreleased has per-slice detail). Kite subscription ACTIVE.
Worktree used for 3.5 was merged and REMOVED — everything is linear on
main; push to origin is manual (user).

**⚠ FIRST ACTION NEXT SESSION (any account): the LAST commit (perf
fixes, 2026-07-11) shipped with 56 targeted live-suite tests green +
cargo gates + bug-hunter LOW-only review, but the FULL three-leg gate
was NOT run before the session budget died. Run, sequentially:**
`pytest -m "not parity and not walkforward"` · `-m parity` ·
`-m walkforward` (from backend/, never concurrent) + `make lint` +
frontend checks — i.e. the make-check equivalent — before building
anything new. Rust + wheel already rebuilt (release, set_levels FFI
live in backend/.venv).

Open threads, in order:
0. **Two LOW hardening fixes from the perf-fix review** (deferred with
   exact recipes in the ledger §Publish-path perf audit — "bug-hunter
   verdict" block): (a) PSUBSCRIBE-blind gating → `pubsub_numpat()`
   publish-everything sentinel; (b) wall-clock watched-set refresh
   decoupled from droppable pulses. Both small; neither blocks the
   soak (no pattern subscriber exists; backpressure case is degraded-
   mode only).
1. **FIRST SOAK RAN 2026-07-10 — PARTIAL; latency verdict OPEN** (full
   honest record: phase-03 ledger §First soak session). Clean hour:
   1.33M ticks / 125,606 candles / 0 skipped; then a self-inflicted
   load-63 incident (pytest+builds on the soak box) starved the consumer
   and Kite dropped the WS; a 4-hour session-limit freeze followed
   (worker down 11:41–15:29). Crash-restart, drain-and-record, and the
   GREATEST-volume merge all behaved as designed; two-header recording
   replayed and pinned (digest in the ledger; replay committed-count ≡
   live exactly). **Re-run a QUIET-BOX soak next trading day for the
   p99 < 10 ms verdict** — same ritual as before, plus: NOTHING heavy on
   the box market-open→close (no pytest/cargo/maturin), don't start the
   backend API while the worker runs, and run the worker via
   **`make live-worker`** (supervisor target, built + smoked
   2026-07-10: exit 0 breaks — never restart-loops after close; exit 4
   waits 60s with the login-ritual prompt; anything else restarts after
   5s; `WORKER_ARGS=--gap-fill` passes through, LIVE_RECORD_PATH via
   env). The smoke also live-validated the 3.5 level pipeline:
   2,049/2,049 stocks' trigger levels applied through the real DB → FFI
   with zero rejections. Perf note: run the publish-path fixes (audit
   report in the ledger) BEFORE the soak if approved — the p99 target
   likely fails without them.
   **Data incident RESOLVED same evening** (ledger §post-close
   forensics): the v1 consumer wrote off-canon candles TWICE (zombie
   09:56–11:06; drowning 13:01→close restart) and resume-point gap-fill
   couldn't heal the midday holes. User-approved delete + full-day
   rebuild from Kite REST executed and VERIFIED: 5m 75/75, 15m 25/25,
   1h 7/7 canon buckets, zero off-canon, 1,880–2,031 stocks per bucket
   (evidence kept in `forensic_ohlcv_{1m,5m,15m,1h}_20260710`).
   **v1-consumer auto-start REMOVED from `app/main.py` lifespan**
   (canary test proven to fail on the old code); the consumer now
   starts ONLY via `POST /broker/kite/consumer/start` — never while the
   worker runs. The quiet-box soak is UNBLOCKED.
2. **Slice 3.5 CORE DONE + MERGED 2026-07-10** (`main` at `70df694`;
   built on branch `slice-3.5-tick-triggers`). Rust trigger engine +
   replayable "lv" level lines + live_levels.py sources + alerts:live
   stream + /ws/live subscribe_alerts fanout; Rust 55 tests, +25
   backend tests; 3.4 golden digest untouched. Reviews: quant-verifier
   FAIL→fixed + bug-hunter BUGS-FOUND→fixed (dup S/R ids HIGH confirmed
   by executed repros both sides; consumer-ack mark_sent; details in
   the ledger §Reviews 3.5); suite 727 green post-fix; `make
   engine-build` run in main (set_levels FFI live).
   **Still open within 3.5:** forming-candle provisional confidence +
   per-style leaderboards (needs the plan-§2 O(1) incremental factor
   design — decide throttled-batch-rescore vs incremental indicators),
   watchlist-scoped fanout (no watchlist model exists yet), alert UI in
   the frontend (useLiveQuotes already tolerates unknown message types).
   Then 3.6 outcome ticks, 3.7 shadow week + full-session soak (30-day
   paper clock).
3. **Session-ops knowledge (this machine):** single-process `make test`
   OOM-killed twice at the gainer golden under desktop load (Chrome+IDE,
   15GB) — run the gate as three fresh legs instead:
   `pytest -m "not parity and not walkforward"` · `-m parity` ·
   `-m walkforward` (sequential, never concurrent — shared test DB).
   Background shells: poll every ~5 min (log growth + `[b]racket`-trick
   process check); pgrep/pkill -f patterns must NEVER appear in their
   own command line (two self-match incidents on 2026-07-09/10).
4. **Profile tuning** (dc1/dc2/multibagger negative; intraday trio
   flagged) — Phase 6 workflow; verdicts pinned in goldens. Wiring
   session context (3.0) was necessary, not sufficient, for activation.
5. Latent LOW calendar items in the phase-02 report backlog (UTC-date
   trading-day walks; `same_day` weekend validity); Muhurat/special-hours
   sessions unsupported by the worker's standard 09:15–15:30 SessionSpec
   (documented, accepted until the calendar carries session hours).
6. `git push` remains manual (credential-free remote by design).

Daily ops: Kite token dies ~6:00 AM IST; ritual =
`cd backend && uv run python scripts/kite_login.py` (terminal-only).
Chain recorder auto-activates while a token is live.

Phase-2 state (closed 2026-07-07): report
`phases/phase-02-strategy-profiles.md`; walk-forward verdicts — rrbo
POSITIVE (+41.3%/+1.97); dc1/dc2/multibagger FLAGGED; intraday trio
FLAGGED (gainer_925 +56.2% AFTER the 8c-4 look-ahead purge). All 8
goldens replay in `make walkforward`.

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
