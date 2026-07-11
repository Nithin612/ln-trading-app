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
| 3.5 | Tick triggers + provisional layer: entry-zone touches, PDH/PDL/S&R crosses, SL/TP proximity, volume bursts, forming-candle provisional confidence, per-style leaderboards @ 2–4 Hz. Redis Streams for alerts (at-least-once); WS fanout by style/watchlist; drop-oldest backpressure for LTP, never for candle-close | **core ✅ 2026-07-10** (branch `slice-3.5-tick-triggers`): Rust trigger engine (`triggers.rs` + `LiveEvent::Trigger`, armed/re-arm hysteresis, `set_levels` preserves state for unchanged ids) · levels as replayable INPUT (`{"k":"lv"}` recording lines; no-lv recordings byte-identical — 3.4 golden digest untouched) · level sources `live_levels.py` (PDH/PDL from 1d, §2.5-width entry zones + SL/TP proximity per active signal, frozen-detector S/R for signal stocks, 5m vburst baselines; 30s refresher thread) · `alerts:live` stream XADD + `/ws/live` `subscribe_alerts` fanout with style filter. Rust 55 tests · +23 backend tests. **Deferred:** provisional confidence + leaderboards (needs the O(1) incremental factor design — plan §2's "ring buffer per close / O(1) provisional"), watchlist fanout (no watchlist model exists), alert UI. Reviews pending (session-limit interrupt) — run quant-verifier + bug-hunter before merge | alerts never gate/mint/modify signals — provisional layer only |
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

## Decisions made this phase

- (3.0) Prev-day context derives from the profile's OWN intraday bars
  (session-aggregated), not the 1d table: NSE's official daily close is a
  last-30-min VWAP ≠ last-bar close, and the walk-forward derives from
  bars — matching it exactly is what keeps live and backtest gates
  identical.

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
