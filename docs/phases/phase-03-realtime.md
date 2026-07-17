# Phase 3 — Realtime v2: tick-to-tick (IN PROGRESS)

**Started:** 2026-07-09 · **Plan:** `docs/UPGRADE_PLAN.md` (Phase 3) ·
**Target:** live-worker + Rust LiveEngine, committed-vs-forming layers,
record/replay harness, tick→publish p99 < 10 ms, one shadow week, then a
full-session soak. **The 30-day paper clock starts when this phase soaks
clean.**

> **Kite Connect subscription is REQUIRED from slice 3.3 onward** (live
> WebSocket is the phase). Slices 3.0–3.2 and the replay side of 3.4 build
> offline. Daily ritual once subscribed:
> `cd backend && uv run python scripts/kite_login.py` (token dies ~6 AM IST).

## Goal

Replace the v1 asyncio-threaded tick path with a dedicated live-worker
process and the Rust LiveEngine: honest tick-to-tick with two deliberately
distinct output layers — **committed** (candle-close, spec-exact, no
repainting, backtestable) and **forming** (tick-level, provisional-labelled,
never enters backtests or P&L) — plus the record/replay harness that makes
any of it provable.

## Slice ledger

| # | Slice | Status | Notes |
|---|-------|--------|-------|
| 3.0 | **Pre-work** (pinned by 8c quant-verifier): fail-closed `_prev_day_hlc` on intraday windows · prev-day + 9:25 cross-section wired into pipeline SetupContext via shared `session_context` · `weight_multipliers` through live scoring (closes the slice-7 gap) · opening-gap measured at session open | **✅ 2026-07-09** | goldens replay byte-stable (9/9, incl. intraday trio); 4 regression canaries proven to fail on pre-fix code |
| 3.1 | Rust LiveEngine core: session-aligned tick→candle state machine (forming/committed), session guard, warmup/gap-fill as data params — pure, no I/O/clocks. Pins the 9:15-anchored 1h bucket canon | **core ✅ 2026-07-09** (engine-core/src/live.rs, 15 tests incl. LCG partition property; canon in ARCHITECTURE.md §Live bucket canon). PyO3 `LiveBook` binding lands with 3.3 host work | the 3.2 SQL rebuild mirrors the canon expression |
| 3.2 | `ohlcv_1h` session-aligned rebuild | **✅ 2026-07-09** — migration `q3r4s5t6u7v8` (delete UTC-floored body, roll up from 11.5M complete 5m bars via shared `app/services/ohlcv_rollup.py`): **1,074,456 rows / 2,036 stocks, anchors exactly 09:15…15:15 IST, zero incomplete**. Interim v1 aggregator floor patched to the 03:45-UTC anchor (identical for 1m/5m/15m; 1h moves to canon) so live minting stays consistent until 3.3. §8 sign-off = walkforward+parity replay green in make check (no golden touches 1h) | downgrade leaves the table EMPTY (documented: pre-rebuild rows were garbage; 5m source re-derives) |
| 3.3 | live-worker process (`app/broker/live_worker.py`, run as `python -m app.broker.live_worker`): KiteTicker thread → bounded `queue.Queue` (drop-oldest tick batches; time pulses share the queue so ordering is replayable) → consumer THREAD → ONE `tradecore.LiveBook` call per batch → sync redis pipeline (`SET ltp:{stock_id}` + LTP/candle PUBLISH) → committed candles via BLOCKING writer queue → writer thread (own loop + own engine) → Postgres upsert → Celery trigger after commit. PyO3 `LiveBook` binding (money strings in / raw i64·1e-4 out). Token-expiry = process exit 3/4 for the supervisor; `--gap-fill` opt-in startup backfill; JSONL record hook = the 3.4 replay input. XADD alerts stream lands with 3.5; indicator warmup lands with 3.5 triggers | **✅ 2026-07-09** (code+tests; first live market soak pending next session — see exit gate) |
| 3.4 | Record/replay harness | **✅ 2026-07-10** — recordings are self-describing (session header + tick/pulse lines in engine order; stale/skipped ticks never recorded); `app/broker/replay.py` feeds them through a fresh `LiveBook` → canonical event stream + sha256 digest; CLI `python -m app.broker.replay <rec> [--emit]` is the soak-day pinning ritual. Synthetic golden committed (61 events / 22 committed; pre-open rejection, volume baseline+reset, per-tf late-tick, pulse closes) + a worker-seam fidelity test proving replay ≡ writer-queue stream. `make replay` in the check chain. Tick→publish `LatencyHistogram` in the worker (fixed buckets, p50/p99/max at shutdown) — **p99 < 10 ms VALIDATION happens on soak day, not in CI** | real-session golden joins after the first soak |
| 3.5 | Tick triggers + provisional layer: entry-zone touches, PDH/PDL/S&R crosses, SL/TP proximity, volume bursts, forming-candle provisional confidence, per-style leaderboards @ 2–4 Hz. Redis Streams for alerts (at-least-once); WS fanout by style/watchlist; drop-oldest backpressure for LTP, never for candle-close | **core ✅ 2026-07-10** (branch `slice-3.5-tick-triggers`): Rust trigger engine (`triggers.rs` + `LiveEvent::Trigger`, armed/re-arm hysteresis, `set_levels` preserves state for unchanged ids) · levels as replayable INPUT (`{"k":"lv"}` recording lines; no-lv recordings byte-identical — 3.4 golden digest untouched) · level sources `live_levels.py` (PDH/PDL from 1d, §2.5-width entry zones + SL/TP proximity per active signal, frozen-detector S/R for signal stocks, 5m vburst baselines; 30s refresher thread) · `alerts:live` stream XADD + `/ws/live` `subscribe_alerts` fanout with style filter. Rust 55 tests · +23 backend tests. **Deferred:** provisional confidence + leaderboards (design PINNED 2026-07-11 — throttled batch rescore of the hot set, see §Decisions; implementation after the Monday soak), watchlist fanout (no watchlist model exists). Alert UI DONE 2026-07-11 (§Alert UI). Reviews DONE 2026-07-10 (quant-verifier FAIL→fixed, bug-hunter BUGS-FOUND→fixed — §Reviews 3.5) | alerts never gate/mint/modify signals — provisional layer only |
| 3.6 | Signal-outcome tick evaluation (entry-zone touch before expiry) recorded now — Phase 6 needs this data | planned | |
| 3.7 | Shadow week (Rust decides, frozen Python double-checks on closes — zero diffs) → full-session soak (memory flat, zero dropped subscriptions, latency budget met) | planned | python engine deletion decision AFTER shadow week (user ruling) |

## First soak session — 2026-07-10 (PARTIAL; latency verdict OPEN)

The first market-hours run of the live worker. Honest record:

- **Session 1 (10:39–11:40 IST):** started mid-session (token ritual done
  08:09; worker launched 10:39 without `--gap-fill` — 2,049 instruments ×
  3 tfs ≈ 34 min of throttled REST was judged worse than a post-close
  heal). Clean for ~50 min: 1,331,556 ticks, 125,606 committed candles,
  0 skipped, 218 stale (snapshot echo, expected), LTP keys + candle
  pub/sub verified end-to-end, recording ~85 MB.
- **Incident (~11:31):** a full pytest suite + review-agent builds were
  started ON THE SAME BOX (session-runner error — the no-heavy-jobs rule
  had only covered compiles). Load hit 63; the consumer starved; in_q
  filled (~10k batches ≈ +300 MB RSS); at 11:38:40 Kite dropped the WS
  (1006) and the worker exited 3 by design, draining and recording its
  full backlog first (fail-safe paths all behaved as built).
- **Gap (11:41–15:29):** the account session-limit froze the supervisor
  (this Claude session) until 15:20 IST; worker restarted 15:29:47,
  caught the session tail, self-exited clean after close. The recording
  carries TWO session headers (crash-restart shape — exactly what replay
  was designed for).
- **Latency:** session-1 histogram is incident evidence, not engine
  evidence (p50 20 ms under ambient build load; p99 ≈ 540 s = queue-stall
  time). **The p99 < 10 ms verdict remains OPEN — needs a quiet-box
  session (next trading day).**
- **Lessons pinned:** (1) NOTHING heavy runs on this box during a soak —
  no pytest, no cargo, no maturin, market open → close; (2) the worker
  needs a real supervisor (systemd/loop script) — a frozen Claude session
  must not cost 4 hours of capture; (3) the v1-consumer hazard resolved
  itself today (the user's backend process died with the box load and its
  zombie consumer with it) but the auto-start in `app/main.py` lifespan
  remains a footgun while a worker runs — do not start the backend during
  a soak session.
- **Salvage value:** multi-session recording integrity, crash-restart +
  drain-and-record paths, GREATEST-volume upsert merge, and stale-tick
  guards all exercised by a REAL incident; morning + midday candle holes
  healed post-close via gap-fill (5m/15m/1h; 1m stays holey — no profile
  reads 1m).
- **REAL-SESSION REPLAY PIN (2026-07-10, two-header recording,
  ~90 MB, kept in gitignored `backend/data/recordings/` — too big for a
  repo golden, so the pin is digest-only):** 1,348,022 lines →
  5,481,858 events, **133,718 committed — EXACTLY the live total
  (125,606 session 1 + 8,112 session 2)**. Digest
  `sha256 3ead00b25d73251dac9214da0ff09823d9abc517794145c72e46bc87187cc469`
  (`python -m app.broker.replay data/recordings/rec-2026-07-10.jsonl`).
  Replay ≡ live proven on real data across a crash-restart boundary.
- **Publish-path latency note (quiet-box tail sample, n=112):** p50
  ≈ 20 ms per batch even without contention — the <10 ms p99 target
  looks at risk from the per-tick `json.dumps` × ~2k-instrument redis
  pipeline, not the engine. Run perf-auditor over `_publish_ltp`/
  `_publish_events` before the next soak.
- **POST-CLOSE FORENSICS — the "zombie" v1 consumer was NOT inert.**
  Per-bucket stock counts show it minted **off-canon candles from 09:56
  to ~11:06 IST** (5m anchors :56/:01/…, 15m :46/:01/:16/:31, 1h 09:46 &
  10:46 — ~1,950 stocks each, `is_complete=true`) before dying with the
  backend process. So today's intraday tables mix THREE writers: zombie
  off-canon rows, live-worker canon rows (10:35–11:35 + 15:25 tail), and
  resume-point gap-fill rows — with real holes (5m 11:30–12:05 and
  14:40–15:20 missing for ~all stocks; canon 09:15–09:55 near-empty).
  Root causes pinned: (1) `app/main.py` lifespan auto-starts the v1
  consumer whenever a valid token exists — the 08:43 uvicorn reload
  armed the zombie (off-canon morning anchors), **and the user's backend
  log shows a SECOND incarnation: the backend was restarted ~13:01 IST
  and its v1 consumer ran DROWNING until close — by 15:28 it was
  inserting the 14:44-IST bucket (44 minutes behind real time) amid
  "Tick queue full; dropped oldest batch" spam.** The afternoon canon
  rows (13:00–14:35, counts tapering 2,035→874) were ITS live mints,
  and the 14:40–15:20 hole is its lag death-spiral — those buckets
  never got processed before close. (2) `gap_fill.detect_and_fill_gaps`
  fills only `MAX(time)+1 → now` per (stock, tf) — it cannot see holes
  BEFORE a stock's newest row, so tail commits at 15:25 masked
  everything. **Evidence snapshotted** to `forensic_ohlcv_{1m,5m,15m,
  1h}_20260710` (1m kept in-place too: no cheap rebuild path, no
  reader — dirty-but-unused, flagged for cleanup with the v1 deletion).
  **REMEDIATION EXECUTED + VERIFIED (user-approved 2026-07-10 evening):**
  deleted today's rows from ohlcv_5m/15m/1h (77,085 / 32,720 / 13,465)
  and reran `--gap-fill` (resume point drops to yesterday → full-day
  refetch from Kite REST, ~40 min). Post-rebuild verification: **5m
  75/75 buckets, 15m 25/25, 1h 7/7 — zero off-canon anchors, zero
  missing, 1,880–2,031 stocks per bucket.** Today's intraday tables are
  canonical again. Before the NEXT soak: remove/flag-gate the v1 consumer
  auto-start (it armed BOTH incarnations; the v1 path is scheduled for
  deletion anyway) and teach gap-fill true hole-detection or accept
  delete-first heals. Subagent/process ops: run agents ONE at a time on
  this box (parallel agents froze it — user directive, in memory).

## Slice 3.0 — pre-work (done 2026-07-09)

The three MEDIUMs pinned in the phase-02 report (§8c addendum item 4) that
had to land BEFORE any intraday profile activates, plus one adjacent bug
found while fixing them:

1. **`_prev_day_hlc` fails closed on intraday windows**
   (`app/profiles/setups.py`). The old fallback used `iloc[-2]` — the
   previous BAR — so "PDH breakout" on a live intraday window would have
   gated on a five-minute range and passed almost anything. Detection is
   data-driven (min consecutive index gap ≤ 1h ⇒ intraday); daily windows
   keep the fallback (1d goldens replay through that exact path).
2. **Live pipeline now builds real session context**
   (`app/profiles/pipeline.py`): per-stock prev-day OHLC aggregated from
   the window's own sessions (fails closed when < 3 sessions are present —
   a 300-bar-capped window may have truncated the earliest), and the 9:25
   cross-section over the resolved universe, consulted only when the
   decision bar starts ≥ 09:20 IST (the look-ahead boundary from 8c-4).
   The per-symbol math was EXTRACTED into `app/profiles/session_context.py`
   and the walk-forward now delegates to it — one implementation on both
   sides (8b aggregate_trades precedent), proven by the 9/9 byte-stable
   golden replay.
3. **`weight_multipliers` reach live scoring** (`app/services/
   signal_service.py` + pipeline): applied via the exact BacktestEngine
   sequence (`run_all_factors → apply_weight_multipliers →
   score_from_factors`); `{}`/None is byte-identical to the frozen path
   (all seeded profiles carry `{}` — zero live behavior change today).
   ENGINE_IMPL=rust refuses multipliers loudly (tradecore.score_signal has
   no such input yet — same fail-loud discipline as the flows guard).
4. **Found & fixed en route:** `eval_opening_gap` measured the "opening"
   gap at the DECISION bar's open on intraday windows (mid-session price,
   not the open). Now measured at the decision session's first bar. No
   seeded profile uses opening_gap on intraday — goldens unaffected.

Tests: +26 functions / 28 cases — 11 pure session-context · 7 evaluator
regressions (9 cases) · 5 pipeline integration (PDH pass/drop canaries,
9:25 ranking, screen-born look-ahead guard, multiplier capture) · 3
services seam. The four behavioral
canaries were run against the stashed pre-fix tree and all fail there
(the drop-canary reproduces the old code minting a suggestion above the
previous BAR's high).

Known conservative-only divergence (quant-verifier INFO, 2026-07-09): on
a live window with fewer than 3 present sessions (new listing / sparse
history) prev-day context fails closed and the suggestion DROPS, while the
walk-forward — which loads full history — would evaluate it. Drops only,
never mints; read golden-vs-live with this and `schedule_approximated` in
mind.

Still open before any intraday profile activates (unchanged from the
walk-forward verdicts): pdh_pdl / orb_15m / gainer_925 are all FLAGGED —
wiring context is necessary, not sufficient. Activation stays a Phase-6
tuning decision.

## Alert UI (3.5 deferred item — DONE 2026-07-11)

Frontend-only; zero contact with the worker/soak path. `AlertBell` in
the topbar + `useAlertStream` (subscribe_alerts protocol: burst-buffered
200 ms flush, 100-cap, 3 s reconnect re-applying the style filter, 4401
= sign-in-again, never a loop) + presentation vocabulary mirroring
`TriggerTag::as_str` and the live_levels meta. +14 tests (frontend 145
total); eslint/tsc clean. Manual smoke against the REAL stack (backend
+ tp_redis, headless Chrome): XADD → badge → panel row with sid→symbol
resolved over REST → style chips → Escape-close; panel verified SOLID
by getComputedStyle probe. Note for replays of the smoke: screenshots
taken <150 ms after open capture the zoom-in entry animation mid-flight
(panel appears displaced) — wait ~400 ms before judging anchoring.

ui-reviewer: **PASS-WITH-NOTES, no HIGH.** Taken same session: badge
switched to the §19.3 accent-bg/accent pill pair (white-on-accent
failed AA in 3 of 5 themes — the one MEDIUM), parseAlert refuses
non-numeric price strings (a ₹NaN row misleads — +test), focus-visible
rings on bell + chips, 10px type floor, the new topbar divider written
in the working v4 syntax, +2 tests (unknown-tag degradation renders
raw strings; 99+ badge cap). Frontend suite 147 green. Deferred to the
migration slice (all pre-existing idiom/token-level): raw-button topbar
chrome + 44px targets, Popover aria-expanded/focus management, daybreak
warning-token contrast, aria-live on the status rows.

Smoke bycatch (recorded, each its own follow-up):
1. **Tailwind v4 broke the `[--color-x]` class idiom repo-wide** — all
   619 occurrences compute to NOTHING (probed: sidebar/topbar/panel
   backgrounds rgba(0,0,0,0); the app survives on body background,
   inherited text color, and inline styles). v4 syntax is
   `(--color-x)`; the new alert files use it; the shared Popover panel
   moved to an inline solid `var(--color-surface)` + border-strong
   (+ Escape-close, which ui.md always required). Dedicated migration
   slice recommended: mechanical rename + visual pass across all 5
   themes; frontend-only — safe any time, even before the soak.
2. Dashboard fires a duplicate-React-key console warning with zero
   alerts involved (suspects: DashboardPage.tsx:275 `key={d}`, :337
   `key={h}`).
3. `make create-admin`'s default email admin@trading.local is REJECTED
   by the login EmailStr validator (.local TLD) — the documented
   bootstrap admin could never log in. Default now admin@trading.com.
4. The vite dev proxy (string shorthand) never forwarded WebSocket
   upgrades — `/ws/live` could not connect in dev at all; `ws: true`
   fixed (prod is same-origin, unaffected).

## Second soak — 2026-07-13 (quiet box; 4 runs; latency measured, stability NOT proven)

Honest record. Four runs, six recording headers (incl. a 15 s
pre-flight); the 315 MB recording (`backend/recordings/
soak-2026-07-13.jsonl`) appended across ALL runs and is intact; the
console log survives only for run #4 (restarts reused `tee` without
`-a` — truncation; runbook fixed: worker needs self-logging).

**Run #4 (14:59–15:40) — CLEAN, the measurement:** ticks 755,623 ·
committed 81,815 · triggers 3,218 · avg_batch 114.1 · **latency p50
7.5 ms · p99 in (20,50] ms · max 85.3 ms · dwell p50 1 ms / p99 2 ms ·
processing p99 (20,50] ms**. DB coverage 14:59–15:29 healthy
(1,750–1,990 stocks/min). Dwell is FIXED (perf-fix validated); the
tail is pure processing, concentrated at minute boundaries (commit
bursts) — exactly the audit's predicted shape. **p99 < 10 ms as
written: NOT MET at 2,055 instruments** (the target was authored for
200–500). Decision pending (user): restate the budget at scale vs
apply the scoped optimizations (unchanged-price SET dedupe,
commit-burst batching) and re-soak.

**Incidents (chronological):**
1. 09:22 — relative LIVE_RECORD_PATH + make's cd-backend crashed the
   recorder open (missed 9:15–9:25); fixed 7092e4f (mkdir parents).
   Residue: later restarts used the relative path from history — the
   recording landed in backend/recordings/ (auto-created), while the
   tee log sat in ./recordings/. Works, but confusing — runbook now
   prescribes "$PWD/…".
2. 10:29 — redis OOM at 512 MB: the WRITER enqueues a Celery
   signal-trigger per committed candle but NO consumer runs during a
   soak → db1 "celery" list grew to 495 MB of TTL-less messages →
   volatile-lru had nothing to evict → ALL publishes refused. Fixed
   live: UNLINK celery (tasks are no-ops today — intraday profiles
   INACTIVE) + runtime maxmemory 3 GB. By close the list had refilled
   to 344 MB / 308,061 tasks (no re-OOM). DESIGN FIX OWED: the
   consumerless enqueue is unbounded TTL-less growth by construction.
3. 11:26 — KiteTicker died (1006, peer dropped TCP). The shutdown then
   WEDGED: latency stats show a ~16.4 min max (queue had been backing
   up since ~11:11 — consumer throughput collapsed, cause not
   identified; run #2's console log is lost), the writer thread died in
   the exit path ("cannot schedule new futures after shutdown" — the
   run_in_executor(writer_q.get) pattern races loop teardown), and the
   drain then ground 5 s per committed candle in the CRITICAL
   writer-dead drop loop for 36 minutes (~430 candles of the 11:11
   bucket dropped one at a time) until manually killed at 12:02. TWO
   exit-path bugs: executor-shutdown race; unbounded slow drain after
   stop_event.
4. Run #3 (12:02–14:58) degraded PROGRESSIVELY: 1m coverage full until
   ~12:55, then partial commits shrinking through 13:00–14:00 (minutes
   with 33/64/2 stocks), near-zero 14:00–14:57, tick-queue drop-oldest
   spam by 14:58. Cause UNKNOWN (console log lost; no in-run
   telemetry). INSTRUMENTATION GAP: stats print only at shutdown — the
   worker needs a periodic in-run stats line (queue depths, writer
   lag, batch p50) to make degradation diagnosable.
5. Post-close: `python -m app.broker.replay` on the full-day recording
   was OOM-KILLED (exit 137) — replay buffers the whole event stream;
   fine on goldens, breaks at 315 MB/full-day scale. Needs streaming
   digest. Digest pin for 2026-07-13 pending that fix.

**Data damage:** 153/375 session minutes have ZERO 1m rows (gaps
9:15–9:25, 9:22–10:41 minus partials, 11:11–12:02 zombie window +
dropped 11:11 bucket, 13:00–14:59 progressive) plus dozens of partial
minutes; 5m/15m/1h correspondingly affected. Rebuild from Kite REST
required (the 2026-07-10 delete+gap-fill procedure).

**bug-hunter on the slate (766050e): one real find, fixed @8c84d29.**
The `run_consumer` finally-block's `writer_q.put(None)` sentinel was
UNBOUNDED — a dead writer + full queue blocks it forever, wedging the
non-daemon consumer so the process never exits and the supervisor never
restarts (the exact class this slate targets; the 45s drain marginally
raised reachability). Now bounded (`_SENTINEL_PUT_TIMEOUT_S`, skip-on-
Full; main()'s writer join covers a dead writer). +1 regression test.
Everything else verified SOUND: bounded-drain loop (all four exit paths
reach flush+sentinel once), `_enqueue_committed` reorder (no busy-spin,
no new data loss), writer `RuntimeError` catch (scoped, can't mask
persist bugs), dispatch gate (covers both v1+v2 callers, no test
depends on firing), monitor (GIL-atomic, daemon), Makefile/compose.

**Fix slate — items 1–3 + ops DONE 2026-07-13 night (commit 766050e
+ 8c84d29, +10 regression tests, live suite 66 green, bug-hunter
reviewed clean after the one fix):**
(1) ✅ consumerless-celery OOM — per-candle Celery dispatch gated behind
`LIVE_SIGNAL_DISPATCH_ENABLED` (default OFF: `send_task` enqueues and
succeeds with no worker, growing a TTL-less list to OOM); compose
maxmemory 512mb→2gb. (2) ✅ writer exit-path race (`RuntimeError` from
the teardown executor-shutdown caught as end-of-stream) + `_enqueue_
committed` checks liveness BEFORE the put (immediate breadcrumb, no
5 s/candle) + `run_consumer` bounded post-stop drain
(`_SHUTDOWN_DRAIN_S=45s`, so a WS-death backlog isn't replayed and the
supervisor restarts promptly). (3) ✅ `run_monitor` heartbeat thread
(queue depths + counters + latency every 30 s) + **`make soak`** target
(absolute `$(CURDIR)` record path, append-tee self-log, clears the
stale broker list — kills the 07-13 ops fumbles); ritual pinned in
`docs/RUNBOOK-soak.md`. **Still open:** (4) streaming replay digest
(replay still OOMs on a full-day recording — exit 137); (5) RE-SOAK for
both the latency ruling and a clean stability pass; (6) run-#3
root-cause once the heartbeat gives in-run telemetry.

**Candle rebuild (2026-07-13 night):** two passes. Pass 1 (unthrottled,
via the existing `startup_gap_fill`) exposed that `fetch_historical`
BYPASSES `ThrottledKite` — ~6000 unthrottled requests drew intermittent
Kite `InputException: invalid token` and left morning-only (2029 stocks,
09:15–13:15) with the afternoon dropped. Pass 2 (throttled via
`ThrottledKite`, full session, ON CONFLICT) SUCCEEDED — final verify
matches the clean 07-10 rebuild exactly: **5m 75/75 buckets (146,815
rows, to 15:25), 15m 25/25 (50,470), 1h 7/7 (14,237)**; afternoon
distinct-stock coverage 2040 (vs 2041 in the damaged forensic copy —
~99.95%). 42/6165 calls failed (front-loaded intermittent invalid-token,
none late; likely stale `kite_instruments` tokens on a handful of
symbols — not chased, immaterial at that coverage). Forensic copies
kept in `forensic_ohlcv_*_20260713`; **1m left empty** (matches the
07-10 rebuild scope; low-value live-only table — the only real residual
gap). 07-13 5m/15m/1h are now trustworthy for walk-forwards; 1d/EOD
were never affected.
LATENT BUG FILED: `fetch_historical` must route through `ThrottledKite`
like every other Kite REST path (trading-domain rule) — the unthrottled
call is the root of the rebuild pain and a lurking rate-limit hazard for
`startup_gap_fill --gap-fill` at scale.

## Third soak — 2026-07-14 (the re-soak: STABILITY PASS; latency confirmed; restart path validated live)

**The run:** first outing of `make soak`, started 09:26:42 — 11.7 min
after open (runbook says pre-09:15; the only cost was data, see below).
Two segments: A 09:26:42→14:18:06 (Kite dropped the WS, 1006), B
14:18:14→15:40:04 (clean `session over`, exit 0 at 15:40:04). Day
totals: **9,045,595 ticks · 828,180 committed candles · 14,097 triggers
· 0 skipped · 0 drop-oldest**. Log `recordings/soak-2026-07-14.log`,
recording `recordings/soak-2026-07-14.jsonl` (587 MB, kept local).

**Stability: PASS.**
- 745 heartbeats at 30 s cadence, exactly ONE gap all day (the restart
  minute itself). Queues 0/0 on 737/745 beats; 8 transient writer_q
  bursts (max 2,015/10,000, all at :15/:30 commit boundaries, each
  drained before the next beat); in_q never above 2. No degradation
  across 6h13m — run-#3's silent decay did not recur, and with the
  heartbeat it could no longer be silent.
- **The 14:18 WS death exercised the whole 766050e slate in
  production**: CRITICAL logged, full stats printed, exit 3 within
  600 ms (07-13 equivalent: 36-min drain wedge + zombie), supervisor
  restart after 5 s, warmup + resubscribe of 2,055 in 8 s, stale-guard
  rejected 266 pre-watermark snapshot ticks, second recording header
  appended, and **no per-minute DB coverage dip in the restart window**
  (14:17/14:18/14:19 = 1,673/1,666/1,671 stocks/min vs 1,669 session
  median).
- Celery-OOM gate HELD: broker list length 0 all day (07-13: 495 MB →
  OOM); redis 2.2 MB used / 3 GB max.
- Recording LOSSLESS: 9,072,094 lines = 9,045,595 ticks (matches the
  worker counters A+B exactly) + 22,386 pulses (exact match) + 2
  headers + 4,109 level lines (+2 append-guard blanks).

**Latency: the 07-13 number is now confirmed steady-state, not a
sick-run artifact.** Three independent measurements agree (07-13 run
#4; today A n=67,931; today B n=17,294): **p50 7.5 ms · p99 in
(20,50] ms · max 98.2 ms (A) / 97.3 ms (B) · dwell p50 1 ms / p99 2 ms
· avg_batch 105–110**. First beat of the day printed the 100 ms bucket
(open burst, n=114), 09:30 printed 20 ms; the other 743 all sat in the
50 ms bucket. Dwell stays noise (perf-fix holds) — the tail is pure
processing at commit boundaries, exactly the 07-10 audit's shape.
**p99 < 10 ms as written: NOT MET at 2,055 instruments.** No more data
is needed — this is now purely the pending ruling (owner: user):
(a) restate the budget at scale, or (b) apply the scoped publish-path
optimizations (unchanged-price SET dedupe, commit-burst batching) and
re-soak.

**Data (the only damage = pre-start window, operator timing):** live
coverage healthy 09:27→15:30 (median 1,669 stocks/min; close minutes up
to 1,995; totals 1h 7/7 · 15m 25/25 · 5m 74/75 · 1m 366/375 buckets).
From the 09:26:42 start (stale-guard watermark 09:24:44): 1m
09:15–09:23 ZERO rows, 09:24/09:25 partial (18/121 stocks); 5m 09:15
missing, 09:20 partial (18), 09:25 short ~1.75 min; 15m + 1h 09:15
buckets present (2,026/2,041 stocks) but opens minted from 09:24:44+
snapshots and volume short ~9.5 min. **Scoped repair DONE same session**
via NEW committed tool `backend/scripts/repair_morning_window.py`
(+6 tests): official 5m refetched for [09:15, 09:30) across the full
active-EQ universe through `ThrottledKite` with ON CONFLICT DO UPDATE —
partial rows must be REPLACED, so `backfill_intraday.py`'s DO-NOTHING
semantics couldn't be reused — then the 15m/1h 09:15 buckets recomputed
as straight 5m aggregates. Results: **5,758 5m bars upserted (09:15
bucket now 1,884 stocks, 09:20 1,934, 09:25 refreshed to official
2,022); 15m 09:15 recomputed 2,030 rows; 1h 09:15 recomputed 2,041**;
14/2,055 stocks failed (intermittent `invalid token`, same front-loaded
pattern as the 07-13 rebuild — immaterial). Spot check: RELIANCE 15m
09:15 == its 5m aggregate exactly (O/H/L/C/V 1290.0000/1298.8000/
1290.0000/1297.3000/693,232). 1m left as-is per the 07-13 precedent
(9 minutes 09:15–09:23 remain empty; low-value live-only table).
07-14 intraday 5m/15m/1h is walk-forward-trustworthy end-to-end.

**bug-hunter on the executed repair (2591e59): tier-A NONE — the
production data is verified right** (it independently re-derived all
2,030 15m + 2,041 1h rows from their 5m children on the live DB: 0
mismatches, 0 orphan buckets, 0 forming rows in the window; the 1,884 +
146 = 2,030 arithmetic reconciles — the 146 are stocks with no 09:15
bar, incl. the 14 failed fetches whose live rows remain
self-consistent; separable only by a plain re-run — **separated same
night: a token-warm re-run failed the SAME 14 with `invalid token`, so
they are deterministic STALE `kite_instruments` tokens, not intermittent
API flake** — the fix is the planned instrument re-sync deliverable, not
retries; immaterial illiquid microcaps until then). Five tier-B/latent
findings, ALL FIXED same session (+2 tests, suite 8 green): (1) HIGH —
recompute hardcoded ONE 15m/1h bucket regardless of `--until-ist`; a
wider window would have left repaired 5m under stale wrong buckets →
`_recompute_buckets` now loops every touched bucket (+ regression test
that fails on the old code). (2) MEDIUM — no mid-session guard;
same-day runs before 15:40 IST would stamp `is_complete=true` on
forming buckets → refused at startup. (3) MEDIUM — the forming-bar test
canary was VACUOUS (PK-collided with a complete bar and was silently
DO-NOTHING-dropped; bug-hunter proved by mutation that removing `AND
is_complete` still passed) → forming bar now the only row in its slot,
fixture existence asserted, mutation now fails. (4) LOW — tripwire only
armed for the first 20 calls; a mid-run token death ground through
every remaining doomed request → consecutive-anywhere with
reset-on-success (+test). (5) LOW — raw `requests` transport exceptions
(re-raised by ThrottledKite after retries) crashed the run →
`_rex.RequestException` in the net (the backfill_intraday lesson).
Also confirmed sound: IST/UTC canon incl. kiteconnect naive-datetime
handling, half-open window edges, RECOMPUTE_SQL determinism + injection
surface (table names unreachable from input), per-stock atomic upserts
with rerun-heals semantics, universe join identical to the live
worker's subscription set, and the aggregate-semantics decision itself
(live 5m volumes telescope exactly into 1h — verified against
candle_aggregator's single `_volume_delta` per tick).

**Still open after today:** (4) streaming replay digest — unchanged
(today's 587 MB recording would OOM the buffering replay; digest pins
for 07-13 AND 07-14 both pending that fix). (6) run-#3 RCA — no
recurrence in 6h13m under the heartbeat; downgraded to
watch-if-it-recurs (it is now observable in-run). (5) re-soak — DONE
(this section); its latency half is the p99 ruling above. Phase-gate:
the "full-session soak clean" criterion is **MET on stability**; the
latency budget line awaits the user ruling.

## Optimization slate — 2026-07-14 night (the (b) ruling, executed same evening)

**User ruling (same day as soak #3): option (b) — optimize + re-soak —
AND restate the budget** (ledger §Decisions; PERFORMANCE.md +
PHASES.md updated: p99 ≤ 50 ms hard at full universe, (10,20] bucket =
the optimization target the re-soak measures).

The two scoped fixes from the 07-10 audit's "decide after the next
soak" list, both in `app/broker/live_worker.py`:

1. **Unchanged-price SET dedupe** (the audit's un-gateable ~11 ms/full-
   batch floor): `_publish_ltp` keeps `_ltp_cache` {stock_id: (price,
   monotonic)} and skips the `ltp:{stock_id}` SET when the price equals
   the last successfully-SET value and that SET is younger than
   `_LTP_RESET_S` (60 s = TTL/10 — the key's worst-case age never
   approaches the 600 s TTL, so the paper-broker contract survives).
   SET fires on first sight, every price change, and the keep-alive
   window; intra-batch duplicates dedupe too (pending-dict), while A→B→A
   inside one batch correctly re-SETs (pipeline order = last write
   wins). The cache learns a SET **only after pipe.execute() returns**
   — a redis blip must not leave the cache claiming a SET that never
   landed (key could expire mid-outage; the next batch heals). The
   channel PUBLISH leg is untouched: still subscriber-gated, still
   per-tick cadence.
2. **Commit-burst batching** (the p99 tail = commit-boundary
   processing): `_enqueue_committed` now puts ONE list per input batch
   instead of one queue put per candle — a :30 close used to pay
   thousands of lock/notify cycles inline in the tick loop.
   `run_writer` unwraps and persists per-candle with per-candle retry
   (one poisoned candle can't take down burst-mates); liveness-checked
   blocking put semantics unchanged (dead-writer fail-loud now counts
   the whole burst). Heartbeat note: `writer_q` depth now counts
   BURSTS, not candles.

Tests: suite grew 30 → 38 (six new dedupe tests incl. the
failed-execute cache-rollback heal and publish-cadence-not-deduped;
burst shape pinned in the committed-candle/writer/drain tests; the
writer-sentinel and recording-reproduces-writer-stream contracts
re-pinned on the list shape). ruff + mypy strict clean.
Measurement: NOT possible off-market — the re-soak (next trading day,
`make soak` per RUNBOOK-soak.md) is the measurement.

**bug-hunter on the slate (same night): BUGS-FOUND, no tier-A — both
findings fixed before commit.** (1) MEDIUM: a redis data loss the
worker CANNOT observe (fast restart / eviction with a surviving
connection) left an unchanged-price key absent up to the full dedupe
window while paper_broker silently fell back to DAILY CLOSE (executed
repro: key None after a simulated flush + unchanged ticks); fixed
three ways — observed execute() failures now `_ltp_cache.clear()`
(assume nothing about which keys survived; the old rollback only
healed the failing batch's own stocks), `_LTP_RESET_S` tightened
60→10 s to bound the unobservable window (~90% of the dedupe win
kept), and the overclaiming comment corrected (+1 regression test:
price returning to a pre-blip value after a blip must re-SET — the
stale surviving cache entry used to dedupe it). (2) LOW test-honesty:
the redis spy recorded ops at BUFFER time with a no-op execute(), so
the new queued/execute seam was unpinnable — a mutant gating execute
on `pending` instead of `queued` (dropping every LTP publish on
deduped batches) passed all 65 tests; the spy is now execute-faithful
(ops land only when execute() runs; failing subclasses drop the
buffer). Everything else verified sound with executed repros: A→B→A
orderings, intra-batch pending precedence, cache-update-after-execute
adjacency, one-now-per-call staleness direction (conservative),
bounded cache memory, silent-stock TTL semantics unchanged, sentinel
ordering, same-list retry on queue.Full (no duplication), per-candle
retry isolation within a burst, no other writer_q readers, replay
untouched (recordings carry ticks/pulses, not writer items). Suite 66
green after fixes (live worker 38 + levels + triggers + replay).

## Fourth soak — 2026-07-15 + 2026-07-16 (re-soak on the optimized worker: STABILITY PASS ×2; budget MET; NO tightening)

Two full sessions on the 8eac05a worker (SET dedupe + commit-burst
batching), run back-to-back for a two-day baseline. Analyzed
2026-07-16 night from `recordings/soak-2026-07-{15,16}.{log,jsonl}`.

**The runs.**
- **07-15:** started 09:18:20 — 3.3 min late again (runbook says
  pre-09:15; cost = data, see below). Segments: A 09:18:22→15:15:50
  (Kite 1006 unclean close), B 15:15:58→15:40:03 (clean `session
  over`, exit 0). Day totals: **9,352,428 ticks · 847,995 committed ·
  15,493 triggers · 0 skipped**. 2,055 instruments.
- **07-16:** started 09:12:31 — **first soak to make the pre-09:15
  window**; 2,056 instruments (universe grew by one). Pre-open held
  correctly: 4 zero-tick heartbeats; `stale` jumped to 2,042 during
  09:12–09:15 (session guard rejecting ~1 pre-open snapshot tick per
  instrument) and NEVER grew after — the counter is benign and now
  understood. Segments: A 09:12:31→14:42:41 (1006), B
  14:42:48→14:42:51 (**double drop** — reconnected, took the 2,461-tick
  snapshot burst, dropped again in 3 s), C 14:42:58→15:40:03 (clean
  exit 0). Day totals: **9,539,362 ticks · 848,693 committed · 14,654
  triggers · 0 skipped**.

**Stability: PASS both days.**
- Heartbeats 762 (07-15) / 774 (07-16) at 30 s; queues effectively
  empty all day both days — in_q never above 1, writer_q peaked at 2
  bursts (07-16; 0 on 07-15), every nonzero beat drained by the next.
  No degradation across either session.
- **Three more Kite 1006 drops, all recovered unattended**: 8 s
  (07-15 15:15), 17 s across the 07-16 double drop — the first
  back-to-back drop we've seen; the supervisor's 5 s loop + warmup +
  resubscribe handled the immediate re-death without operator action.
  Running tally: 4 drops in 3 soak days, all between 14:18 and 15:16 —
  an afternoon Kite-side lifecycle event, now demonstrably routine.
- Recordings LOSSLESS both days: 07-15 = 9,352,428 t + 22,887 p
  (both exactly match worker counters A+B) + 2 headers + 4,110 lv
  (2×2,055); 07-16 = 9,539,362 t + 23,232 p (exact, A+B+C) + 3
  headers + 6,168 lv (3×2,056). 606 MB / 619 MB, kept local.
- Celery-OOM gate held: broker list 0 and redis at 2.23 MB when
  verified post-run 07-16 night (dispatch gate default-OFF; no
  consumer ran; `make soak` cleared the list at each start).

**Latency — the optimization verdict (honest): budget MET, target
bucket NOT reached, gate stays 50 ms.** Every segment on both days
finished with total p99 in **(20,50]** — same bucket as
pre-optimization, so the **(10,20] tightening criterion is NOT met**
and the budget line stays **p99 ≤ 50 ms** as restated. What the slate
DID move, against soak #3 (A n=67,931 / B n=17,294 vs 07-15 A
n=84,367 / 07-16 A n=77,878): **processing p50 7.5 → 5.0 ms on both
days' main segments**, and on 07-15 A the **processing p99 landed in
(10,20]** (07-16 A stayed (20,50]); max latency 98.2 → 89.1 (07-15) /
91.5 (07-16 A). p50 7.5 ms, dwell p50 1 / p99 2 ms, avg_batch 106–116
all unchanged. One 135.4 ms outlier (07-16 C, n=11,137) right after
the double restart — the snapshot burst (segment-B avg_batch 307.6 =
~3× normal) is the obvious suspect; cumulative p99 never left (20,50].
Reading finer than this is histogram-limited: the bucket ladder jumps
20 → 50, and 07-15's cumulative p99 oscillated 20↔50 across 15 beats,
i.e. true p99 sits just above 20 ms. OPTIONAL follow-up if we ever
revisit: one added 30 ms bucket would make the next comparison
readable.

**Data.**
- Coverage complete both days: 5m 75/75 · 15m 25/25 · 1h 7/7 canon
  buckets, ~1,950–2,036 stocks per 5m bucket.
- **07-15 open bucket was thin** (worker up 09:18:22): 5m 09:15 had
  2,030 stocks but only ~40.6 M shares vs 217.1 M in 07-16's 09:15 —
  ~2/3 of the highest-volume bucket of the day missing, opens minted
  from 09:18:22 ticks. **Scoped repair EXECUTED same night** via the
  committed `repair_morning_window.py --day 2026-07-15 --until-ist
  09:20` (exactly the one damaged 5m bucket). Results: **1,872 5m
  bars upserted — 5m 09:15 now 2,032 stocks / 185.9 M volume (was
  40.6 M, 4.6×; in line with 07-16's 217 M open bucket); 15m 09:15
  recomputed 2,039 rows; 1h 09:15 recomputed 2,041 rows.** Spot
  check: RELIANCE 15m 09:15 == its 5m aggregate EXACTLY
  (1294.1000/1310.4000/1294.1000/1305.3000/1,122,637). **16/2,056
  stocks failed, all `invalid token` — the deterministic stale
  kite_instruments set has grown 14 → 16** (illiquid microcaps,
  immaterial; their live-minted rows remain self-consistent; the
  planned instrument re-sync is the fix). 07-15 5m/15m/1h is
  walk-forward-trustworthy end-to-end.
- **07-16 5m 14:40 bucket volume-undercounted** (15.3 M vs neighbors
  31.6/43.3 M): both restarts landed inside it, and the
  GREATEST-volume merge keeps the larger partial, not the sum. Same
  class as soak #3's 14:18 restart — ACCEPTED per that precedent
  (coverage intact, prices merged correctly, volume short ~17 s +
  merge semantics). If restart-bucket repair ever matters, the fix is
  generalizing repair_morning_window's window start (it hardcodes
  09:15) — noted, not planned.
- One thin live-only **1m** bucket on 07-15: 15:15 = 1,051 stocks vs
  ~1,870 neighbors. Timing artifact, now understood: the drop hit at
  15:15:50, so segment A's forming 1m candles died uncommitted and
  the bucket was repopulated only by the reconnect snapshot's 2 s of
  runway. Soak #3 saw NO dip because its drop landed 6 s into the
  minute (46 s of post-restart runway); 07-16's 14:42 double drop
  also barely dipped (1m 14:42 = 1,687) for the same snapshot reason.
  Left as-is per the 1m live-only precedent; 5m/15m/1h unaffected
  (5m 15:15 = 2,013 stocks, healthy).

**Phase-gate reading:** the End-Phase-3 "full-session soak clean"
criterion is now MET on BOTH halves — stability (three consecutive
soak days) and latency (budget p99 ≤ 50 ms measured MET on two days of
the optimized worker). No open ruling. Remaining Phase-3 work is the
queued thread list (replay digests — now FOUR recordings pending the
streaming digest — ThrottledKite for fetch_historical,
kite_instruments re-sync, provisional confidence, 3.6, 3.7).

## Streaming replay digest — 2026-07-17 (thread closed; all four soak recordings pinned)

**The fix (open thread #4/#5 since 07-13):** `python -m
app.broker.replay` buffered the whole recording as dicts, the whole
event stream as a list, and the canonical lines as a third list —
exit-137 OOM on any full-day recording, which is why every soak digest
since 07-13 was "pending". `app/broker/replay.py` is now streaming
end-to-end: `iter_recording` (single-pass validated parse; the
torn-tail-before-header tolerance needs exactly ONE line of lookahead,
so each non-blank line is processed when its successor arrives),
`iter_events` (generator over the unchanged FFI call pattern — one
single-tuple `on_ticks` per recorded tick line, `set_levels` per lv,
`on_time` per pulse, fresh LiveBook per header), and
`replay_stream(path, emit)` → ReplaySummary(lines, events, committed,
triggers, digest) doing parse → FFI → sha256-update → optional
incremental emit in constant memory, with the emit file written
ATOMICALLY (`.tmp` + rename on success, unlink on failure). The old
public API (`load_recording` / `replay_events` / `replay_file` /
`canonical_lines` / `events_digest`) survives as thin list wrappers
over the same generators — one parsing implementation, and the pinned
golden digest is byte-identical through both paths. CLI output now
also counts triggers (reconciles against worker counters).
Measured: **~38 MB peak RSS flat across all four recordings** (the
old path OOMed a 15 GB box); ~3 min per full-day file.

**Tests 11 → 19** (`make replay`): streaming-vs-buffered digest
equality on the pin, emit-vs-golden byte equality, single-pass parse
canary (yields the header of a file whose tail is garbage — the
buffered loader could never), `iter_events` laziness canary (first
event before the feed is exhausted — the exit-137 mutant class),
torn-tail through the streaming path, headerless/empty refusals,
emit-clobber regression (below). ruff + mypy strict clean; targeted
live suite (replay + live_worker + live_triggers) 64+ green.

**bug-hunter (same session): BUGS-FOUND, no tier-A — digest/pin
invariant proven by executing OLD vs NEW implementations** (identical
sha256 on the pinned golden and on a non-ASCII payload; 20-case
old-vs-new parse differential 19/20 byte-identical incl. torn+blank
pairing, CRLF, first-line-torn). Findings: (1) MEDIUM emit hazard —
the first cut opened `--emit` with truncate BEFORE replaying, so a
failed run clobbered the target (e.g. a pinned golden → 0 bytes) or
left a partial stream that looks complete; FIXED with atomic
`.tmp`+rename (+2 regression tests: target untouched on unreadable
path AND on mid-replay ReplayError, no stray .tmp). (2) LOW accepted:
error-precedence drift on doubly-broken files (headerless+garbage now
fails on the header check first — fail-faster, message-only, no
consumer matches on it). (3) LOW documented: zero-event `--emit` now
writes an empty file, not the old spurious `b"\n"` (consistent with
the empty-stream digest; no zero-event golden exists). (4) test-
honesty gap (a secretly-buffering replay_stream passed the suite) —
closed with the `iter_events` laziness canary.

**The pins (streaming digest ritual, run 2026-07-17 00:30–01:00 IST,
quiet box).** Lines = validated items (headers + lv in, torn/blanks
out); committed/triggers reconciled against the worker's logged
counters summed across segments:

| Recording | lines | events | committed | triggers | reconciliation | sha256 |
|---|---|---|---|---|---|---|
| soak-2026-07-13.jsonl (315 MB, 6 headers, backend/recordings/) | 4,850,967 | 19,764,553 | 493,235 | 13,265 | PARTIAL — only run #4's console counters survive that day (81,815 committed / 3,218 triggers of these totals); the recording is intact and replays cleanly end-to-end, pinned as deterministic engine input | `88da0c167af30dc89b4e7c099fd6d3c53721670a151643ac407e48dda929a67c` |
| soak-2026-07-14.jsonl (587 MB, 2 headers) | 9,072,092 | 36,981,894 | 828,180 | 14,097 | **EXACT** — committed 656,733+171,447, triggers 9,995+4,102; lines = 9,045,595 t + 22,386 p + 2 h + 4,109 lv | `5bfdcd35a3b539391eaf931506ce703d3e6d80760b18d0a7f501b54a2a237bf8` |
| soak-2026-07-15.jsonl (606 MB, 2 headers) | 9,379,427 | 38,221,468 | 847,995 | 15,493 | **EXACT** — committed 809,716+38,279, triggers 13,808+1,685; lines = 9,352,428 t + 22,887 p + 2 h + 4,110 lv | `3fba10ff0ce9f745edd599386f127335a0726d8c4a0dca77ae0ae4c2aee63c7f` |
| soak-2026-07-16.jsonl (619 MB, 3 headers) | 9,568,765 | 38,981,553 | 848,693 | 14,654 | **EXACT** — committed 729,442+270+118,981, triggers 11,407+0+3,247; lines = 9,539,362 t + 23,232 p + 3 h + 6,168 lv | `cff17a555295d63d74c1a4f343537b24ff70e09be26cf95eebc047823c1ec1d5` |

Replay ≡ live on every recording with surviving counters — the
LiveEngine's determinism contract holds at full-day, full-universe,
multi-restart scale.

## Watchlists (3.5 deferred item — DONE 2026-07-11, same session)

Full vertical slice, zero worker contact: `watchlists` +
`watchlist_items` (migration `r4s5t6u7v8w9`, reversibility PROVEN
up→down→up on dev), ownership-scoped service + CRUD API,
`subscribe_alerts {"watchlist": id}` on /ws/live (validated before any
state mutates — fail closed with an error frame; stock set snapshots at
subscribe; empty watchlist ≠ unscoped, pinned by tests), /watchlists
manager page + AlertBell scope selector (both filters re-applied on
reconnect). +13 backend / +10 frontend tests. Unblocks the
provisional-confidence hot set ("watchlist stocks" clause in
§Decisions). Harness bycatch FIXED: the app's pooled engine ×
per-TestClient loops broke any DB-touching WS path on the second test
("Task attached to a different loop") — test_ws_alerts.py disposes the
app engine per test; prod unaffected (one loop per process).

Browser smoke (real stack, strict in-panel assertions after a first
FALSE-POSITIVE pass that matched page text outside the panel) caught
three real defects, all fixed with regression tests: (1) selecting an
option in a Select nested inside the Popover closed the panel and
swallowed the selection (nested floating layers portal outside the
panel ref — outside-mousedown now ignores select layers; canary-proven
test); (2) SimpleSelect's trigger rendered the raw VALUE (latent —
every prior caller had value≡label; watchlists select by id) and
leaked `__empty__` when no ''-option exists — label resolved
explicitly with placeholder fallback; (3) the fuzzy q-search ranks
alphabetically, so exact tickers never surfaced in a top-8 list —
client-side re-rank (exact → symbol-prefix → name-prefix) over 50
rows. Final verified pass: ONE in-panel alert row (in-list stock),
out-of-list alert filtered server-side, "Momo" shown in the scope
trigger, zero console errors.

bug-hunter: **BUGS-FOUND → all fixed same session, +2 regression
tests.** MEDIUM (CONFIRMED, executed repro): a watchlist id ≥ 2^63
(JSON ints are unbounded) reached asyncpg as a DataError and tore down
the WHOLE WS socket instead of the fail-closed error frame — ids are
now type-strict (bool/float rejected) and int64-bounded at parse, and
_watchlist_sids failures degrade to an error frame (a DB hiccup at
subscribe must never kill the LTP/candle stream). LOWs: REST id params
+ StockRef bounded (422, was 500); create/rename IntegrityError
backstop (race past the pre-check → 409, was 500). Verified sound:
the closure/reassignment scope swap has no await between styles+sids
mutations (reader can never see a mixed state); session lifecycle
leak-free on disconnect; migration head/types/indexes; producer↔reader
sid contract; frontend payloads in-range by construction.

## Tailwind v4 token migration (DONE 2026-07-11, same session)

All 898 `[--color-x]` class sites (46 files) converted to the v4
`(--color-x)` form via one regex pass; the two code comments that
reference the old syntax deliberately left. Empirical verification
(headless Chrome, the smoke harness): all five themes now compute
opaque, theme-distinct sidebar/topbar/surface colors (previously
rgba(0,0,0,0) across the board); opacity modifiers on var colors
compile per theme (`border-(--color-profit)/20` → `oklab(… / 0.2)`);
daybreak finally renders as a real light theme; carbon's amber accent
system correct; zero console errors. Riders folded in: DashboardPage
header dup-key fixed (two "" action columns → positional keys; warning
verified gone in-browser); StocksPage filter badge → accent-bg/accent
AA pair; Popover trigger aria-expanded + aria-haspopup. 147 tests
green; eslint + tsc clean. Note for future styling: tokens.css
registers `--color-*` inside `@theme`, so Tailwind also generates named
utilities (`bg-surface-3` etc.) — a possible future idiom; `(--var)`
was chosen as the minimal-risk mechanical change.

ui-reviewer on the migration: **PASS-WITH-NOTES** — regex-replay proved
the conversion byte-mechanical; tailwind-merge v3.6.0 treats paren ≡
bracket in every conflict group; all four riders verified (badge pair
computed 5.1–7.0:1 AA across themes). Taken same commit: StatusPill
active/pending solid `-bg` fills (alpha deviation became LIVE with the
migration), UI_GUIDELINES syntax examples + §13.1 audit greps updated
(bracket hits now flagged as regressions), stale comments reworded,
Popover aria-expanded test added. **UI polish backlog (pre-existing,
recorded for a future pass):** (1) default Button white-on-accent fails
AA in midnight/carbon/ocean (theme `--color-primary-foreground` or
accent-bg pair); (2) DashboardPage StatCard `${color}20` hex-alpha
appended to var() strings = invalid CSS, chips render transparent; (3)
signals table lacks PriceCell flash + memoized rows on the live tick
path, LTP unconditionally bull-green; (4) `toLocaleString`/`toFixed`
sweep across Dashboard/Stocks/Portfolio/Journal/Screener/pagination/
sparkline → lib/format.ts; (5) Kite banner hardcoded rgba/yellow-500;
(6) UsersPage role-badge hardcoded purple triplet → `.badge-*` class;
(7) Badge/SelectItem "Loading…" text vs Skeleton; (8) user-avatar.tsx
hardcoded gradient + string-concat className.

## Decisions made this phase

- (soak #3 ruling, **user 2026-07-14**) **Latency budget RESTATED and the
  optimization slate chosen — option (b) + restatement together.** The
  written p99 < 10 ms was authored for 200–500 instruments; three
  independent full-scale measurements (07-13 run #4, 07-14 segments A+B)
  pin steady-state p50 7.5 ms / p99 (20,50] / max <100 ms at 2,055
  instruments with dwell fixed (p99 2 ms) — the tail is commit-boundary
  processing, not queueing. New budget: **p99 ≤ 50 ms tick→publish at
  full universe (hard gate)**; the shipped optimizations (unchanged-price
  SET dedupe + commit-burst batching, this section below) target the
  (10,20] bucket — if the re-soak lands it, the gate tightens to 20 ms.
  PERFORMANCE.md budget table + PHASES row updated; UPGRADE_PLAN's 10 ms
  mentions (§Phase-3 deliverables) stand as historical intent,
  superseded by this entry.
- (3.0) Prev-day context derives from the profile's OWN intraday bars
  (session-aggregated), not the 1d table: NSE's official daily close is a
  last-30-min VWAP ≠ last-bar close, and the walk-forward derives from
  bars — matching it exactly is what keeps live and backtest gates
  identical.
- (3.5-deferred, **pinned 2026-07-11, user-approved**) **Provisional
  confidence + per-style leaderboards = throttled batch rescore of a
  bounded hot set; the plan-§2 O(1) incremental-indicator sketch is
  REJECTED for now** (revisit only if hot-set scale proves insufficient
  on Phase-6 data, not on assumption). Why rescore: (1) parity by
  construction — the SAME frozen scorer sequence (`run_all_factors →
  apply_weight_multipliers → score_from_factors`) on the same
  300-completed-bar window canon with the forming bar appended, so the
  provisional score CONVERGES EXACTLY to the committed score at candle
  close; no third implementation of the edge (an incremental twin needs
  its own Wilder/EMA parity program, and a drifting confidence preview
  is a wrong number about money). (2) Factor coverage — S/R clustering,
  pivots, divergence, and the 9:25 cross-section are structurally
  windowed; "pure" incremental ends up hybrid anyway; batch reuses
  `session_context.py` unchanged. (3) Hot-path isolation — runs on a
  refresher-style thread (the 30 s levels pattern: own thread, own
  loop, own session), reading forming candles via ONE new FFI snapshot
  getter (`LiveBook.forming_snapshot`, GIL released); ZERO new work on
  the consumer thread; the p99 budget stays untouched. (4)
  Reversibility — the WS/UI surface is compute-agnostic; incremental
  can replace the internals later without a surface change. Pinned
  semantics: provisional scores are a DERIVED OBSERVABILITY VIEW —
  never engine events, never in recordings/replay, never in backtests
  or P&L (constraint #3), provisional-labelled end-to-end; hot set per
  style = active-signal stocks + near-trigger stocks + watchlist
  stocks (once the model exists); cadence = refresher-clock throttle
  (1–5 s target), full-universe cadence decided by `/perf-bench`
  numbers; confidence integer canon unchanged
  (`trunc(|normalized|×100)`). Implementation starts only AFTER the
  Monday soak (it touches the worker process); the slice starts from
  this paragraph.

## Reviews (slice 3.0)

- **quant-verifier: PASS-WITH-NOTES** (no HIGH/CRITICAL). All three notes
  applied: `_ist_date` explicit IST conversion in setups.py (removes the
  NSE-hours UTC-date coincidence dependency), the <3-sessions divergence
  documented above, CHANGELOG test count corrected.
- **bug-hunter: BUGS-FOUND, 4 LOW/latent, none blocking — all addressed:**
  (1) top_gainer_925 exact-tie ranking was dict-insertion-order dependent
  (live planner order vs walk-forward alphabetical) → deterministic
  (pct, symbol) sort key; gainer_925 golden replayed byte-stable after the
  change (no ties in the pinned corpus). (2) multiplier guard placement
  blacked out rust+intraday multiplier profiles → guard now applies only
  to the true tradecore 1d path; the intraday python fallback applies
  multipliers (+1 seam test). (3) latent: cross-section series keyed by
  bare symbol corrupts under dual-exchange listings (unreachable while
  ingestion is NSE-only) → loud duplicate-symbol warning. (4) latent:
  1m + prev-day setups can never assemble context (375-bar session >
  300-bar cap) → loud per-run warning; profile stays fail-closed.
- Noted for activation discipline: a 1h profile with top_gainer_925 is
  live-permitted but walk-forward-refused (TIMEFRAME_TABLES excludes 1h) —
  golden-before-activation catches it; the "9:25" screen on 1h feeds is
  consulted at 10:15 (no look-ahead, just a misnamed datum).
- test-guardian: queued for the 3.3 slice (canary-vs-stash proof below
  already demonstrates the new tests bite).

## Publish-path perf audit (2026-07-10 post-close; fixes NOT yet applied)

perf-auditor measured the tick→publish window at 5214d8d (micro-benches
on the dev box; full model + numbers in the audit run, distilled here).
A full 2,000-tick batch costs ≈ 127 ms, of which **~112 ms is the Redis
publish leg** — and most of that is spent on nobody:

- 80 ms: building (`json.dumps` ×8,000 forming events) and publishing to
  `candle:*` channels with **zero subscribers** (ws.py subscribes per
  watched symbol only);
- 26.5 ms: the LTP leg (2,000 SET + 2,000 PUBLISH; the pure-Python
  redis parser costs ~2× a raw socket — hiredis is NOT installed);
- 5.9 ms: line-buffered recorder (flush syscall per line);
- engine + FFI ≈ 4–6 ms; the Rust core itself is noise (1 ms).

Measurement caveats found: the histogram stamp includes GIL queue-dwell
(5–10 ms with one pure-Python peer thread — the kiteconnect parser is
exactly that); buckets jump 10→20 ms so "p50 20" means (10, 20]; pulse
items are unstamped and their minute-boundary commit cost lands on the
NEXT batch. And the documented p99 < 10 ms budget was written for
200–500 instruments — the soak ran 2,049 (4–10× the stated scale).

**FIXES APPLIED 2026-07-11 (user-approved "go"; committed same day):**
items 1–4 below all landed — subscriber-gated publishes (watched set
refreshed per pulse via PUBSUB CHANNELS; LTP KEY always SET), hiredis
installed (parser confirmed active), recorder block-buffered with one
flush per queue item (SIGKILL repro proved the file stays line-aligned
— no torn tail), dwell/processing histogram split + 7.5/15 ms buckets +
avg-batch in the shutdown line, sys.setswitchinterval(0.002) in main,
and the Rust per-tick scratch-buffer polish (LiveBook.on_tick no longer
allocates). +3 behavioral tests (SET-without-publish default, pulse
refresh, latency split); 56 targeted live-suite tests green.
**bug-hunter verdict: BUGS-FOUND, LOW only — two deferred hardening
items for the NEXT session (neither affects any live path today):**
(a) LOW CONFIRMED latent: PUBSUB CHANNELS cannot see PSUBSCRIBE — a
future pattern subscriber would silently receive nothing. Contract
comment added at the channel constants (exact SUBSCRIBE only); the
robust fix is a `pubsub_numpat()` check in `_refresh_watched` that sets
a publish-everything sentinel (watched=None) when pattern subscribers
exist, with `if watched is not None and channel not in watched` at both
gates. (b) LOW PLAUSIBLE: the refresh rides pulses, and pulses are
droppable under queue-full backpressure (pulser put_nowait + drop-
oldest eviction) — under sustained saturation a new subscriber's ≤1 s
pickup window stretches; fix = wall-clock refresh inside process_item
(`if started - self._last_refresh >= 1.0`) instead of the pulse branch.
**Both CLOSED 2026-07-11 same session, recipes verbatim** — +2
regression tests, each stash-canary-proven to FAIL on the pre-fix code;
(b) also closed a startup gap (watched set began empty, so the first
second of forming events published to nobody until the first pulse —
now the first item of any kind refreshes). Targeted live suite 50
green. bug-hunter re-review of the closing diff: **CLEAN, zero
findings** — executed repros: numpat/second-channel-read raises keep
the previous watched value WHOLE (local build, assign only after both
reads) with the engine unstarved and the LTP key still SET; redis=None
and method-less spies early-return; a None-unaware-gate wrong
implementation is caught by the pattern test; −inf first-item refresh
+ 1 s cadence verified; the only redis-hang exposure (no
socket_timeout) is pre-existing and unchanged in class. The deferred
FULL three-leg gate had run green on 293a7d0 immediately before (731
backend / 131 frontend / 16 parity / 9 walkforward / 11 replay;
`make check` exit 0).
Everything else verified sound: flush-vs-crash semantics, latency
arithmetic (latency = dwell + processing exactly), pulse-branch
ordering, ungated LTP SET/alerts, hiredis types, Rust scratch identity,
switchinterval scope.

**Original audit fix plan (for reference; est. p99 ≤ 5–8 ms at
observed batch sizes after 1–3):**
1. Subscription-gate channel publishes (refresh watched set via
   `PUBSUB CHANNELS`, 0.27 ms/pulse) — saves ~85 ms/full batch; only
   observable change: a client subscribing mid-second may miss ≤1 s of
   updates (REST reconciles — already the documented reconnect model).
2. Install hiredis (~2× on every remaining pipeline; zero behavior
   change).
3. Recorder block-buffering + one flush per item (crash-loss window one
   line → one batch, ≤1 s; replay's torn-tail tolerance covers it).
4. Measurement honesty: dwell/processing split stamps, 7.5+15 ms
   buckets, log effective batch size; optional setswitchinterval.
Explicitly REJECTED: coalescing forming events inside Rust — Kite's
conflation makes it a ~0 win AND batch-scoped coalescing would break
replay byte-exactness (batch boundaries aren't recorded; replay feeds
one tick per call). At true 2,049-tick full batches the un-gateable LTP
SET floor (~11 ms even with hiredis) still brushes the budget → restate
the budget at soak scale or add unchanged-price SET dedupe (decide
after the next soak's numbers).

## Reviews (slice 3.5)

- **quant-verifier: FAIL → all findings fixed same session.** HIGH
  (confirmed by executed FFI repro): rank-indexed S/R ids (`SR_BASE_ID+i`
  per signal) duplicated on stocks with ≥2 active signals → all-or-
  nothing validation rejected the stock's whole level list → its alert
  layer silently dead for the session (and `mark_sent`-at-enqueue made
  it permanent). Fixed: S/R computes once per (stock, timeframe); ids
  are identity-derived (sha256 of timeframe:zone_type:price, range
  disjoint-by-construction from signal ids). MEDIUMs: level payloads
  could be lost silently (drop-oldest eviction / engine rejection after
  producer-side mark_sent) → the ack moved to the CONSUMER
  (`on_levels_applied` → `mark_sent` under a lock, fired only on engine
  accept; unacked stocks re-send every cycle, loud); `_active_signals`
  gained ORDER BY id (order-sensitive change detection churned
  recordings). LOW/INFO: statics restricted to the subscription set;
  vburst configs whose threshold truncates to 0 and cross re-arm bands
  ≥100% refused at validation; CHANGELOG splice repaired. Clean bill on:
  §2.5 zone-width mirror, frozen-code isolation, no look-ahead/repaint,
  money discipline (incl. the Decimal-quantized float boundary for S/R
  alert thresholds), PDH/PDL-from-1d soundness.
- **bug-hunter: BUGS-FOUND — same HIGH independently confirmed (executed
  repro both sides), same eviction MEDIUM (executed repro), plus:**
  `_apply_levels` catch broadened to any per-stock exception (a
  malformed payload must not strand the chunk's other stocks); S/R id
  identity fix doubles as the armed-state/dedupe-identity fix for rank
  reshuffles; alert XADDs pipelined (one round trip per batch — an
  open-auction burst must not serialize hundreds of RTTs inside the
  latency-measured window). Verified sound: refresher loop×pool
  discipline, redis-py 7.4 cancellation safety for the WS XREAD reader,
  last_id advancement across filtered entries, fresh-book-per-header
  replay isolation, trigger placement after the candle pass, 48-bit id
  collision bounds. +2 regression tests (two-signals-one-stock passes
  the real FFI; unacked levels re-send until consumer ack).

## Reviews (slice 3.4)

- **bug-hunter: BUGS-FOUND — 1 HIGH, 2 MEDIUM, 2 LOW; all addressed, +5
  regression tests.** HIGH: the recorder was load-bearing (a disk-full
  write aborted batches BEFORE the engine — candles/LTP starved for the
  day) → recording is fail-open and happens only AFTER the engine
  accepts a batch, which also removes the bad-price batch asymmetry
  (LOW #5). MEDIUM: default buffering + torn crash tails could poison a
  whole multi-session file → line-buffered recorder, newline-prefixed
  header, and a single tolerated artifact shape in load_recording (torn
  line immediately before a header). MEDIUM: "make replay is DB-free"
  was FALSE (the tests/ conftest connects and truncates) → claim
  corrected; replay runs in the standard harness, serialized like every
  pytest run. LOW: per-kind shape validation with file:line ReplayError.
- Sound per the review: batch-boundary erasure (engine on_ticks ≡
  per-tick loop), fresh-book-per-header ≡ live restart semantics, stale
  filter runs before recording, digest canonicalization (ints only),
  golden internally consistent (digest re-derived independently;
  epochs = 09:15/15:30 IST).
- Gate-run bycatch: the Phase-0 chain-selection fixtures hardcoded
  expiry 2026-07-09, which expired overnight — first suite run after
  the rollover flipped "nearest expiry". Fixed wall-clock-relative.

## Reviews (slice 3.3)

- **bug-hunter: BUGS-FOUND — 1 CRITICAL, 1 HIGH, 5 MEDIUM, 3 LOW; the
  CRITICAL and one MEDIUM were CONFIRMED by executed repros. All fixed
  same session, each with a regression test:**
  1. CRITICAL — writer exited on (stop AND empty) and raced the
     consumer's final flush: candles committed during shutdown were
     stranded unpersisted. → sentinel contract: the consumer owns a None
     end-of-stream marker; the writer drains until it, timing-immune.
  2. HIGH — `--gap-fill` work was silently ROLLED BACK (gap_fill never
     commits; the bootstrap session close discarded every fetched row
     while logging success). → `startup_gap_fill` commits; regression
     test proves rows survive a rollback.
  3. MEDIUM — redis publishes ran BEFORE the engine and unprotected: a
     redis blip dropped batches pre-engine while the recorder had
     already logged them (replay divergence). → engine first, writer
     queue second, redis last inside try/except.
  4. MEDIUM — clean shutdown's own ticker.stop() fired on_close →
     exit code 3 → supervisor restart-loops all evening. → stop-guard.
  5. MEDIUM — writer dropped a candle on any DB error, log-only. →
     3× retry with backoff, then an error-level manual-backfill
     breadcrumb with the full payload.
  6. MEDIUM — mid-session restart: Kite's subscribe snapshot echoes
     stale ticks; a fresh book re-minted persisted buckets and the
     upsert clobbered real volume with 0. → 120s stale-tick guard
     (host-side, counted) + `volume = GREATEST(...)` in the upsert.
  7. MEDIUM — blocking writer_q.put could wedge the consumer forever if
     the writer died at startup. → liveness-checked put (5s timeout
     loop; dead writer ⇒ log CRITICAL, count, stop for restart).
  8. LOW — drop-oldest race could raise queue.Full inside the Twisted
     callback → drain-and-retry loop. LOW — recorder now closed by the
     consumer (owner), not main. LOW (accepted, documented): session
     bounds are the standard 09:15–15:30 — special-timing sessions
     (Muhurat) are out of scope until the calendar carries hours;
     holidays are naturally inert.

## Gate evidence (accumulating)

- 3.0: `make walkforward` 9 passed / 427s on the refactored tree
  (2026-07-09); gainer golden replayed again post-tie-break fix (268s,
  byte-stable); ruff + mypy strict clean; canary-vs-stash proof recorded
  above.
- 3.1 core: `cargo clippy --all-targets -D warnings` clean · engine-core
  lib tests 40 passed (15 new live:: tests incl. the 5,000-tick LCG
  partition property over all four timeframes).
- 3.4: `make replay` 7 passed (golden byte-identical + determinism +
  validation refusals); worker-seam fidelity test (replay ≡ writer queue
  with stale/unknown ticks in the live input); latency histogram unit
  tests. Digest pinned: `da288d24…`.
- 3.3: binding + worker seams: +5 FFI-contract tests (money round-trip
  exact, fail-loud prices, reject counters, close-flush canon) · +10
  worker tests (LTP key/channel contracts against a real LiveBook,
  committed→writer-queue exactness, pulse commit + record ordering,
  drop-oldest backpressure, Decimal-exact upsert + conflict merge).
  NOTE: first REAL market-hours soak has not run yet — schedule it for
  the next trading session (worker + old consumer must not run
  simultaneously against the same tables).
- 3.2: migration applied on dev 2026-07-09 (~50s); table verified
  post-rebuild: 1,074,456 rows / 2,036 stocks / anchors only
  09:15…15:15 IST / 0 incomplete. +6 tests (5 rollup with injected
  as_of cutoff — canon buckets + stub OHLCV exact, forming hour
  excluded, idempotent never-replace, delete-first replaces :30 rows,
  artifact bars excluded — and the anchored-floor regression).
  OPERATIONAL: restart the backend before the next session open — a
  running pre-patch process would re-mint :30-anchored 1h rows.
