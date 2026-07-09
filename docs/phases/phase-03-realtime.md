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
| 3.3 | live-worker process: KiteTicker thread → `queue.Queue` → consumer thread → ONE PyO3 call per tick batch → sync redis pipeline (`SET ltp:{stock_id}` + PUBLISH + XADD). Token-expiry-as-restart choreography, warmup from DB (batched), gap-fill | planned | **needs Kite subscription** |
| 3.4 | Record/replay harness: recorded tick sessions → byte-identical engine event streams; `make replay` in CI; latency histograms (tick→publish p99 < 10 ms) | planned | replay tests are the only ground truth — no working baseline exists |
| 3.5 | Tick triggers + provisional layer: entry-zone touches, PDH/PDL/S&R crosses, SL/TP proximity, volume bursts, forming-candle provisional confidence, per-style leaderboards @ 2–4 Hz. Redis Streams for alerts (at-least-once); WS fanout by style/watchlist; drop-oldest backpressure for LTP, never for candle-close | planned | |
| 3.6 | Signal-outcome tick evaluation (entry-zone touch before expiry) recorded now — Phase 6 needs this data | planned | |
| 3.7 | Shadow week (Rust decides, frozen Python double-checks on closes — zero diffs) → full-session soak (memory flat, zero dropped subscriptions, latency budget met) | planned | python engine deletion decision AFTER shadow week (user ruling) |

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

## Gate evidence (accumulating)

- 3.0: `make walkforward` 9 passed / 427s on the refactored tree
  (2026-07-09); gainer golden replayed again post-tie-break fix (268s,
  byte-stable); ruff + mypy strict clean; canary-vs-stash proof recorded
  above.
- 3.1 core: `cargo clippy --all-targets -D warnings` clean · engine-core
  lib tests 40 passed (15 new live:: tests incl. the 5,000-tick LCG
  partition property over all four timeframes).
- 3.2: migration applied on dev 2026-07-09 (~50s); table verified
  post-rebuild: 1,074,456 rows / 2,036 stocks / anchors only
  09:15…15:15 IST / 0 incomplete. +6 tests (5 rollup with injected
  as_of cutoff — canon buckets + stub OHLCV exact, forming hour
  excluded, idempotent never-replace, delete-first replaces :30 rows,
  artifact bars excluded — and the anchored-floor regression).
  OPERATIONAL: restart the backend before the next session open — a
  running pre-patch process would re-mint :30-anchored 1h rows.
