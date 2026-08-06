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
| 3 | Realtime v2 — tick-to-tick | **▶ in progress** (started 2026-07-09) | [phase-03](phases/phase-03-realtime.md) | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, latency budget p99 ≤ 50 ms tick→publish at full universe (restated 2026-07-14; original 10 ms was authored for 200–500 instruments). **Kite subscription required from slice 3.3.** Slice 3.0 (pre-work MEDIUMs) ✅ 2026-07-09 |
| 4 | F&O analytics | **▶ backend done 2026-08-06** (branch `phase4-fo-analytics`; UI = Phase 5) | [phase-04](phases/phase-04-fo-suggestions.md) | 4.1 chain/PCR/max-pain/basis/VIX-regime · 4.2 Rust BS/Black-76 IV+Greeks (`tradecore`) + IV-rank · 4.3 option-selling engine (defined-risk index-only; breakeven-POP; expectancy report-only=VRP; fail-closed VIX veto; user-calibrated `SellRules`). Follow-ups: confluence direction-tilt, event/ban gate (=deferred Market Context Engine), Kite SPAN margin, forward-validation dashboard (P6) · 🧭 **Nautilus doc** §9 — Greeks as a first-class data type; options/accounting (margin) refs |
| 5 | UI overhaul | planned | — | new sidebar IA, slate theme default, 4 style pages, chain ladder, virtualized live tables @60fps · 🧭 **Nautilus doc** §4.2 — cache-then-publish lets UI subscribe without touching producers |
| 6 | Outcome tracking + strategy lab v2 | planned | — | per-style hit-rate/expectancy dashboards, factor attribution, Rayon weight tuning + promotion workflow · 🧭 **Nautilus doc** §7 — mimalloc on batch backtest sweeps; §4.3 richer bar aggregations for research |
| 7 | Live-trading hardening | planned | — | Kite orders behind trading_mode + 30-day gate, kill switch, reconciliation, VPS runbook · 🧭 **Nautilus doc** §6 — **SLICE 1 = RiskEngine single-gate** (test-first, equivalence-pinned) → then BrokerAdapter port · order FSM (Denied vs Rejected) · reconciliation |

> **🧭 Nautilus doc pointers** (added 2026-08-01): before starting and at the
> phase-gate of Phases 4–7, consult `docs/NAUTILUS_TRADER_ANALYSIS.md` for the
> adopt/adapt/avoid items relevant to that phase (§6 gap-analysis · §9 India
> adaptations · §8 don't-copy). **Phase 7 opens with slice 1 = the RiskEngine
> single-gate consolidation** (test-first, equivalence-pinned) — it closes the
> caller-side circuit-breaker seam before the live-order path exists (the exact
> class of bug that gave v1 Phase 7 its four integration defects).

**▶ CONTINUE HERE (next session, any account):** Phase 3 IN PROGRESS —
**slices 3.0–3.5-core ALL DONE and on `main`** (3.0–3.3 on 2026-07-09,
3.4 on 2026-07-10, 3.5 core + first-soak ops + publish-path perf fixes
2026-07-10/11; ledger + all review records: `phases/phase-03-realtime.md`;
CHANGELOG Unreleased has per-slice detail). Kite subscription ACTIVE.
Worktree used for 3.5 was merged and REMOVED — everything is linear on
main; push to origin is manual (user).

**✅ 2026-07-11 (Saturday session): the deferred FULL three-leg gate
ran GREEN on the perf-fix commit exactly as shipped** — 731 backend /
131 frontend / 16 parity / 9 walkforward / 11 replay, plus
ruff·mypy·eslint·tsc and cargo fmt·clippy·test; `make check` exit 0.
**Both LOW hardening fixes from the perf-fix review then landed same
session** (ledger recipes verbatim): (a) `PUBSUB NUMPAT`
publish-everything sentinel — a pattern subscriber can no longer be
silently starved by CHANNELS-based gating; (b) watched-set refresh is
wall-clock inside `process_item` instead of riding droppable pulses
(also closes the startup gap: first-second forming events used to
publish to nobody until the first pulse). +2 regression tests,
stash-proven to FAIL pre-fix; targeted live suite 50 green;
bug-hunter re-review CLEAN (executed repros).
**Same evening (user-approved):** the provisional-confidence design is
PINNED (ledger §Decisions — throttled batch rescore of a bounded hot
set on a refresher thread; O(1)-incremental rejected; implementation
AFTER the soak) and the **3.5 alert UI is DONE** (topbar AlertBell +
useAlertStream; smoked against the real stack; ledger §Alert UI).
**Late session, budget-extended: the Tailwind v4 token migration is
DONE (thread 3, `10a9d2b` — all 898 broken sites; 5-theme verified;
ui-reviewer PASS-WITH-NOTES with the polish backlog recorded) and the
WATCHLIST slice is DONE (`cb2092d` — model→migration→API→WS
fanout→UI; bug-hunter MEDIUM fixed with executed repro; end-to-end
browser-verified server-side alert filtering; ledger §Watchlists).**
Frontend 161 / backend 744-ish tests green at session end; the only
3.5 remainder is the provisional-confidence implementation (post-soak,
design pinned).
**SOAK #2 RAN 2026-07-13 — measured but not proven; HARDENING FIXES
SHIPPED SAME NIGHT** (full record: ledger §Second soak). Run #4 clean
40 min → p50 7.5 ms · p99 (20,50] · dwell FIXED; **p99<10 ms NOT met at
2,055 instruments — user ruling pending** (restate at scale vs optimize
+ re-soak). The day's four stability failures are FIXED (commit
766050e, +9 tests, bug-hunter reviewed): Celery-OOM gate, writer
exit-race, 36-min drain wedge, and a heartbeat + `make soak` target.
07-13 candles rebuilt from Kite — 5m/15m/1h full (75/25/7 buckets,
~2040 stocks, matches the clean 07-10 rebuild); only 1m left empty
(low-value); 1d/EOD never affected.
**SOAK #3 RAN 2026-07-14 (`make soak`, first outing) — STABILITY PASS**
(full record: ledger §Third soak). 9.05M ticks / 828k candles / 0
skipped across 6h13m; 745 heartbeats, queues ~0 throughout; a 14:18
Kite WS drop exercised the whole 766050e fix slate live (exit-3 →
8 s restart, no DB coverage dip, second recording header); Celery list
0 all day; recording lossless (tick+pulse counts == worker counters
exactly). Latency CONFIRMED steady-state across both segments: **p50
7.5 ms · p99 (20,50] · max <100 ms · dwell p99 2 ms — p99<10 ms still
NOT met at 2,055 instruments; the ruling is now purely a user
decision** (restate at scale vs optimize + re-soak — no more data
needed). Only data damage: the pre-09:15 start was missed (worker up
09:26:42) → first ~12 min thin/absent; REPAIRED same session via the
new committed `backend/scripts/repair_morning_window.py` (+6 tests) —
official-5m refetch + 15m/1h recompute; 07-14 5m/15m/1h now
walk-forward-trustworthy (ledger §Third soak).

**RULING MADE 2026-07-14 evening (user): option (b) + restatement —
EXECUTED same night** (commit 8eac05a; ledger §Decisions + §Optimization
slate): budget now **p99 ≤ 50 ms @ full universe** (PERFORMANCE.md), and
both scoped optimizations shipped with bug-hunter review clean-after-
fixes (SET dedupe w/ 10 s keep-alive + observed-failure cache clear;
commit-burst batching; live suite 66 green). Same night: morning-repair
re-run proved the 14 failures are deterministic STALE kite_instruments
tokens (re-sync deliverable), not API flake.

**RE-SOAK RAN TWICE — 2026-07-15 + 2026-07-16 (optimized worker
8eac05a): STABILITY PASS ×2; BUDGET MET; NO TIGHTENING** (full record:
ledger §Fourth soak). 9.35 M + 9.54 M ticks, 848 k committed candles
each day, 0 skipped, queues never past 2/10,000; three more Kite 1006
drops (incl. the first back-to-back double drop, 07-16 14:42) all
recovered unattended in 8–17 s; both recordings lossless. Latency
verdict (honest): every segment's total p99 still in **(20,50]** →
the (10,20] tightening criterion NOT met, budget line stays **p99 ≤
50 ms** — but the slate did move the interior (processing p50
7.5→5.0 ms both days; processing p99 into (10,20] on 07-15's main
segment; max 98→89 ms). **The End-Phase-3 "full-session soak clean"
criterion is now MET on both stability and latency — no open ruling.**
Data: 07-15 started 3.3 min late → thin 09:15 open bucket, REPAIRED
same night (`repair_morning_window.py --day 2026-07-15 --until-ist
09:20`); 07-16 started 09:12:31 (first pre-09:15 soak) — only blemish
is the volume-undercounted 5m 14:40 bucket from the double restart
(GREATEST-merge keeps the larger partial; accepted per the 07-14
precedent).

**✅ STREAMING REPLAY DIGEST — DONE 2026-07-17 (ledger §Streaming
replay digest):** `app/broker/replay.py` is streaming end-to-end
(iter_recording/iter_events/replay_stream + atomic emit; old API =
thin wrappers, golden digest byte-identical); ~38 MB flat RSS, ~3 min
per full-day recording (was exit-137 on a 15 GB box). Replay suite
11 → 19; bug-hunter no tier-A (MEDIUM emit-clobber fixed +
regressions). **ALL FOUR soak recordings pinned; replay ≡ live EXACT
on every recording with surviving counters** (07-14: 828,180/14,097 ·
07-15: 847,995/15,493 · 07-16: 848,693/14,654 committed/triggers all
exactly matching worker counters; 07-13 partial-reconciled by design —
runs 1–3 console logs were lost that day). Determinism contract holds
at full-day, full-universe, multi-restart scale.

**✅ THROTTLEDKITE ROUTING — DONE 2026-07-17 (ledger §ThrottledKite
routing):** `fetch_historical` deleted; gap-fill fetches through ONE
shared `ThrottledKite` (full-universe fill now paces ~3 req/s ≈ 35 min,
documented as post-outage repair, not bulk rebuild). bug-hunter found
the diff clean AND three pre-existing latents in the same seam — all
fixed + stash-proven same session: UTC-as-IST fetch window (mid-session
gap-fill was a silent no-op — requested windows shifted 5.5 h into the
past), poisoned-transaction silent COMMIT-as-ROLLBACK data loss (now
commit-per-instrument + rollback), dead-session-token grind (now aborts
CRITICAL at first TokenException; stale-instrument InputExceptions stay
isolated). Suites 49 green + full non-parity leg.

**✅ KITE_INSTRUMENTS RE-SYNC — DONE 2026-07-17 (ledger
§kite_instruments re-sync):** root cause was upsert-only sync — rows
absent from Kite's dump (= dead instruments) were never deleted; 1,584
carcasses accumulated and the "16 stale tokens" were 15 stocks moved
to NSE's T2T series (token rotated) + 1 delisted (AURIGROW) — split
corrected 2026-07-17 during the (c) execution — whose leftover
plain-symbol NSE rows kept joining the universe.
`sync_instruments` now sweeps rows absent from the dump (watermark +
partial-dump tripwire at 50%); EXECUTED live: 60,751 upserted / 1,582
swept / forensic snapshot kept; worker join 2,056 → 2,037 — soaks and
repairs no longer touch dead instruments by construction. **Surfaced
for user decision (ledger §Decisions): 296 active master stocks are
T2T-series (`-BE`) listings the join has NEVER covered** — include via
suffix mapping, accept exclusion, and/or deactivate the ~15 truly-dead
master rows.

**✅ T2T UNIVERSE RULING — MADE + EXECUTED 2026-07-17 (user: (a)+(c);
ledger §Decisions + §Universe deactivation):** (a) the 296 T2T
(`-BE`-series) stocks stay excluded from live coverage — self-healing
exclusion (daily sync + plain-symbol join re-cover any stock NSE
returns to the EQ series automatically); they remain active master
rows. Future re-inclusion path recorded in §Decisions + memory: option
(b) suffix-mapping SCOPED to the Investment engine if it graduates in
Phase 6. (c) EXECUTED via new committed
`scripts/deactivate_dead_stocks.py` (+4 tests, T2T-canary): 15 ghost
rows deactivated (14 dead-everywhere incl. GUJGASLTD/JBCHEPHARM/
RELINFRA-class corporate deaths + v1 noise like NIFTYNXT50; 1
BSE-only mover AVAILFC), forensic_stocks_deactivated + documented
reversal; active master 2,348 → 2,333. Corrected en route: the "16
stale tokens" were 15 T2T series-moves + 1 delisting (not "12 BSE + 4
delisted").

**⚠ INCIDENT (pre-existing, discovered 07-17): EOD INGESTION DOWN
SINCE 2026-07-02** — Celery worker/beat never ran in the v2 era;
ohlcv_1d (+ FII/DII etc.) frozen at 07-02; the 07-15/16 soaks'
prev-day trigger levels came from 07-02 dailies; screener read
2-week-old state. **✅ RESOLVED 2026-07-18** — root-cause fix: EOD
beat tasks are now SELF-HEALING (services/eod_catchup.py heals every
missing session ≤21d lookback, interior holes included); `make worker`
added (celery worker -B, part of the daily ritual — stop it during
soaks; missed evenings heal on the next run). Backfill EXECUTED
07-03→07-17: ohlcv_1d 11/11 sessions (~2,030–2,046 rows/day),
fo_bhavcopy 11/11 (~33–38k rows/day), india_vix_daily 11/11; CA sweep
quarantined 4 corporate actions from the gap (KRISHANA+MBAPL ≈5:1
splits 07-03, MWL ≈10:1 07-10, GOLDIAM ≈4:3 bonus 07-10 — pending
review). FII/DII: live NSE endpoint serves ONLY the latest day and a
FLAT shape the old parser didn't know (parsed to zero records
forever) — parser fixed (+regression test), 07-17 captured; 07-02→
07-16 permanently unavailable from this source (historical fetcher =
Phase 4, factor scores missing days as zero by design). Full detail:
phase-03 ledger §EOD restart.

**✅ PROVISIONAL CONFIDENCE + LEADERBOARDS — DONE 2026-07-18 (ledger
§Provisional confidence + leaderboards): SLICE 3.5 IS NOW COMPLETE.**
Refresher-thread batch rescore per the pinned design (frozen scorer on
the forming-appended window canon; convergence to the committed score
pinned by test); `LiveBook` frozen+Mutex with a `forming_snapshot` FFI
getter (GIL-released, deadlock-impossible lock scoping); per-style
leaderboards SET(TTL)+PUBLISH with signal rows never clipped;
`subscribe_provisional` WS fanout + REST reconciliation + dashboard
ProvisionalPanel (provisional-labelled end-to-end). +21 backend / +12
frontend tests, all real seams (incl. run_cycle e2e through the real
tradecore book). Worker thread behind `live_provisional_enabled`.

**✅ SLICE 3.6 OUTCOME TICKS — DONE 2026-07-19 (@fc50483; ledger
§Outcome ticks + §Reviews outcome ticks).** Direction-aware SL/TP touch
cross levels joined the trigger set (BUY: SL=cross_down/TP=cross_up;
SELL mirrored; outcome truth = touch, not proximity); `signal_outcomes`
replaced with the tick-level first-touch schema (monotonic ladder open →
entry_touched → tp_first/sl_first/expired_*, crash-window upgrades
toward truth; reversible migration `s5t6u7v8w9x0` up→down→up proven; the
v1 EOD shape was dead — 0 rows, no code); durable alerts-stream
consumer-group recorder in the worker (ack-after-commit, PEL crash
recovery, per-entry SAVEPOINT poison isolation, behind
`live_outcome_recorder_enabled`); expiry sweeper finalizes lapsed
signals each 5-min beat (epoch-floored); REST /signals/{id}/outcome +
SignalDetailModal Outcome strip. Reviews: bug-hunter 2 MEDIUM + 3 LOW
fixed; quant-verifier HIGH (redelivery reorder) fixed + gap-through-SL/
at-level limits documented with a **user ruling QUEUED (§Decisions)**.
Gate 829/16/9 backend + 177 frontend. Observability only — never feeds
scoring/sizing/gating/backtests.

**✅ SLICE 3.7 SHADOW-COMPARE HARNESS — DONE 2026-07-19 (@25011bb;
ledger §Shadow compare + §Reviews).** `app/services/shadow_compare.py`
re-scores each committed 1d close under BOTH engines through the one
`score_signal` (explicit `impl=` — no global toggle, no reimplementation)
and reports decision/direction/confidence diffs; EOD sweep over raw
`is_active` (== nightly), per-stock error isolation. `scripts/
shadow_week.py --day` writes a gitignored report, exits nonzero on any
diff/error. SCOPE = base flow-free 1d decision (excluded flows stamped;
frozen Python not deletable until flows reach tradecore). EXECUTED
07-17 vs real DB: 2,293/2,293 matched exactly, 73 emitted signals all
agreeing. quant-verifier + bug-hunter both fixed (toggle race removed).
Gate 840/16/9 + 177 frontend.

**▶ NEXT ACTION = SLICE 3.7 LIVE RUN — LIVE-GATED (needs market days,
cannot run overnight):** (1) SHADOW WEEK — run `scripts/shadow_day.sh
<day…>` (wrapper over `shadow_week.py`, appends PASS/FAIL to
`backend/shadow/shadow_week.log`) once per day AFTER the evening EOD
beats land the close (~19:30 IST — equities EOD 18:40, nightly 19:15;
4:30 PM is too early, the bar isn't ingested yet); zero diffs required
(day-one 07-17 already clean). A gap can be caught up in one evening —
the EOD catch-up heals the backlog, then run the wrapper across the
backfilled days. (2) full-session SOAK — already MET ×2 (07-15/16).
(3) the 30-day paper clock STARTS at 3.7 (starts when `make live-worker`
runs the live path). Then the Phase-3 exit gate (`/phase-gate`).
Pre-open ritual: start `make worker` (from repo ROOT, not backend/)
before 18:30 IST so the evening beats self-heal + generate; then
`make live-worker WORKER_ARGS=--gap-fill` pre-open (its own gap-fill
heals the intraday hole for the subscribed universe — no
`backfill_intraday.py` needed). Watch the provisional cadence (overrun =
tune `live_provisional_refresh_s`/hotset cap) and the outcome recorder
(`XPENDING alerts:live outcome-recorder` ~0). **User rulings CLEARED
2026-07-23 (§Decisions, both RULED):** outcome-tick gap-through-SL =
(a) now + (c) Phase 6; the 4 CA quarantines = keep flagged, re-inclusion
folded into the Phase-4/6 adjusted-history migration.

Open threads, in order:
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
   with zero rejections. Perf state: publish-path fixes AND both LOW
   hardening items are applied and full-gate-validated — the soak now
   measures the fixed path; pin the NEW-format shutdown stats line
   (dwell/processing split + avg batch size) in the ledger, and recall
   the audit caveat: at true 2,049-tick full batches the un-gateable
   LTP SET floor (~11 ms) still brushes the budget — restate the
   budget at soak scale or add unchanged-price SET dedupe, decided on
   the soak's numbers.
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
   **Still open within 3.5:** ONLY forming-candle provisional
   confidence + per-style leaderboards — design DECIDED 2026-07-11
   (ledger §Decisions: throttled batch rescore of a bounded hot set;
   implementation after the soak). Alert UI DONE 2026-07-11 (§Alert
   UI); watchlists + watchlist-scoped fanout DONE 2026-07-11
   (§Watchlists — bug-hunter MEDIUM fixed with executed repro). Then
   3.6 outcome ticks, 3.7 shadow week + full-session soak (30-day
   paper clock).
3. **Tailwind v4 token-class migration — ✅ DONE 2026-07-11 (same
   session it was discovered):** all 898 broken `[--color-x]` sites
   (46 files) converted to the v4 `(--color-x)` form; verified in
   headless Chrome across all five themes (opaque theme-distinct
   surfaces — previously rgba(0,0,0,0) everywhere; `/20` opacity
   modifiers compile per theme; zero console errors; daybreak renders
   as a true light theme for the first time). Riders: dashboard
   dup-key warning fixed (two "" action columns in the static header
   array → positional keys), StocksPage filter badge → accent-bg/accent
   AA pair, Popover aria-expanded/haspopup. Still deferred to a future
   UI pass (ledger §Alert UI): raw-button topbar chrome + 44px targets,
   Popover focus management, daybreak warning-token contrast, aria-live
   status rows.
4. **Session-ops knowledge (this machine):** single-process `make test`
   OOM-killed twice at the gainer golden under desktop load (Chrome+IDE,
   15GB) — run the gate as three fresh legs instead:
   `pytest -m "not parity and not walkforward"` · `-m parity` ·
   `-m walkforward` (sequential, never concurrent — shared test DB).
   Background shells: poll every ~5 min (log growth + `[b]racket`-trick
   process check); pgrep/pkill -f patterns must NEVER appear in their
   own command line (two self-match incidents on 2026-07-09/10).
5. **Profile tuning** (dc1/dc2/multibagger negative; intraday trio
   flagged) — Phase 6 workflow; verdicts pinned in goldens. Wiring
   session context (3.0) was necessary, not sufficient, for activation.
6. Latent LOW calendar items in the phase-02 report backlog (UTC-date
   trading-day walks; `same_day` weekend validity); Muhurat/special-hours
   sessions unsupported by the worker's standard 09:15–15:30 SessionSpec
   (documented, accepted until the calendar carries session hours).
7. `git push` remains manual (credential-free remote by design).

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
