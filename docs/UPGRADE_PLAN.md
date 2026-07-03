# Trading Platform — World-Class Upgrade Plan (v2)

> **Status:** approved 2026-07-03 · Phase 0 in progress. Per-phase results live in `docs/phases/`.
> This document is the *why* behind the v2 upgrade; `docs/PHASES.md` tracks live status.

## Context

The platform is further along than it feels: Phases 0–11 of the original plan are built with ~453 unit/integration tests (auth, stock master, screener, categories, EOD + FII/DII ingestion, the 14-factor confluence engine, dashboard, Kite WebSocket plumbing, paper trading with circuit breaker, strategy lab, journal, portfolio). What's missing is exactly what you named: no per-style pages (Intraday/Swing/F&O/Investment), no F&O capability at all, signals that only update via a slow candle-close→Celery→pandas round-trip, and pure-Python math that can't support tick-rate computation or large tuning sweeps.

But a deep adversarial review (line-verified against the repo) found something more important: **the "live" pipeline has never worked end-to-end**, and there are real bugs in already-built code. So this plan is not just "make it faster and prettier" — it repairs the foundation, then builds the upgrade on it.

**Honesty note, once:** no system guarantees "high profits." This plan maximizes signal quality, reaction speed, risk discipline, and measurement (so tuning is evidence-based, not vibes). The 30-day profitable-paper-trading gate before live trading stays — and note: fixing the sizing bug below **restarts that clock**, because existing paper history was computed at 1/100th intended size.

---

## What the deep review found (fix before building on top)

**Critical — live path is dead on arrival** (`backend/app/broker/tick_consumer.py`):
1. `_on_ticks_thread` calls `asyncio.get_event_loop()` on the KiteTicker thread — raises `RuntimeError` on Python 3.12; ticks never reach the queue (line ~93).
2. `text(...).format(table=...)` — `TextClause` has no `.format`; first candle event kills the processing loop (line ~217).
3. Candle upserts are `flush()`ed but never committed — live candles invisible to signal generation, transaction held open all day (lines ~197-201).
4. `paper_broker.py:30` reads Redis key `ltp:{stock_id}` but the consumer only `PUBLISH`es to channel `ltp:{instrument_token}` — nothing ever SETs the key, so intraday SL/TP monitoring silently runs on stale EOD closes.

**Critical — elsewhere:**
5. **Position sizing 100× too small**: `signal_tasks.py` divides risk_pct by 100, then `risk.py:compute_quantity` divides by 100 again. Every Celery-generated signal risks 0.02% instead of 2%.
6. **The venv is dead** (snap GC'd the uv-managed interpreter) — the 453 tests can't currently run. Rebuild with non-snap `uv python install 3.12`.
7. **1h candle table has two time bases**: live aggregation floors to UTC hours (9:30/10:30 IST candles) while Kite gap-fill writes 9:15/10:15 session-aligned candles into the same table. 1h signals and any engine warmup from it are corrupted until rebuilt session-aligned.
8. **No signal dedup/idempotency** — a persistent setup would insert a near-identical signal every candle close.
9. Redis is one instance with `allkeys-lru` serving as Celery broker + pub/sub + cache — memory pressure can silently evict queued tasks.
10. Backtests run synchronously inside an async API handler — freezes every request and the live WS while running.

**Spec drift — code vs SIGNAL_ENGINE.md (the edge), needs your adjudication before Rust goldens are generated** (each has a recommended default = align code to spec):
- Volume factor always returns +0.5 on surge; spec says it only counts when direction matches (today it *dampens* bearish confluences).
- RSI code adds ±0.4 bands at <30/>70 that are not in the spec.
- Backtest places SL from 20-bar min/max; live uses pivot swings (N=5) — backtest doesn't test live behavior. Pick one canon.
- The expiry sweeper (spec §5) doesn't exist in the beat schedule; "5 trading days" is faked as 7 calendar days (no NSE holiday calendar anywhere).
- Backtest fills are flattering: exits *at* SL even when price gapped through it; never checks SL/TP on the fill candle.
- **Window canon**: Python evaluates factors on exactly the last 300 completed candles; an incremental engine has infinite memory — Wilder-family indicators differ enough to flip threshold-adjacent factors (RSI 29.99 vs 30.01, ADX 24.9 vs 25.1, confidence 69.9 vs 70.0). Must be decided explicitly, not by accident of porting. Recommendation: canonize "last 300 completed candles" (ring buffer recomputed per close for committed signals; O(1) incremental only for the provisional tick layer).

These adjudications get a dedicated decision checkpoint during Phase 1 golden-fixture generation, presented with concrete backtest impact per choice.

---

## Architecture decisions

### 1. Rust compute core (`engine/`), embedded via PyO3 — honest rationale

Cargo workspace: **`engine-core`** (pure, no I/O: incremental indicators, the 14 pattern detectors, pivots/Dow/S&R/zones/Fib, confluence scorer, risk sizer on i64 scaled 1e-4 to match `Numeric(12,4)`, backtest loop Rayon-parallel, Black-Scholes IV/Greeks) + **`engine-py`** (PyO3/maturin wheel `tradecore`) + **`engine-cli`** (native binary for replay/bench without Python).

The honest speed argument: the tick-path math is *not* the bottleneck (500 instruments ≈ 500–2000 ticks/sec — trivial). The killer is the **backtest/tuning loop**: today's engine re-slices and recomputes full-window pandas-ta per candle — O(n²), and weight-grid/walk-forward search over minute data is simply unusable in Python (and multiprocessing doesn't save it: pickling/IPC per task + GIL). Rust makes the lab 100–1000× faster; reusing the same compiled engine live is then nearly free and **eliminates the live-vs-backtest drift bug class this repo already exhibits**. Rayon capped at ~6 threads (i7-1355U thermals), per-stock streaming to respect 15 GB RAM.

**Migration safety & sunset policy** (no permanent dual-engine for a solo dev):
1. Freeze `app/analysis/` when parity work opens (bugfix-only via approved spec changes).
2. Generate **committed golden fixture files** from the frozen Python on real NSE candles + synthetic edges (pandas-ta 0.4.71b0 pinned and recorded in fixtures). The files become the oracle — the Python code becomes deletable.
3. Tiered parity gates: 1e-9 relative (EMA family), 1e-6 (Wilder family), **exact equality on factor scores and confidence integers, zero signal decision diffs on 2y × Nifty50**.
4. One shadow week live (Rust decides, Python double-checks on candle close, diffs logged; zero decision diffs required).
5. Then delete the pandas factor code and the `ENGINE_IMPL` flag in the same release. F&O analytics are Rust-only from day one (validated against py_vollib/hand-computed goldens).
6. Exact-replication details pinned in the port spec: `int()` truncation of confidence, zero-score sentinel → `Option<f64>`, multibagger append-only-when-positive, pivot ties (`==` counts), greedy order-dependent S/R clustering, S/R warmup by recomputation (not DB reads).

### 2. Realtime v2 — honest tick-to-tick, boring concurrency

A dedicated **live-worker process** (systemd-style restart; the *daily* Kite token expiry is designed as a process restart + warmup + gap-fill, not an in-process reconnect). No asyncio in the hot path — two of the four live-path bugs were asyncio/thread impedance:

```
KiteTicker thread → queue.Queue → consumer thread
  → ONE PyO3 call per tick batch (not per tick) into Rust LiveEngine
  → sync redis-py pipeline: SET ltp:{stock_id} + PUBLISH + XADD alerts stream
Persistence off the hot path: Redis stream consumer writes candles to Postgres (real commits).
```

Two output layers, deliberately distinct:
- **Committed signals** — candle-close only, exactly per spec (no repainting, backtestable, idempotent via unique key + supersede rule). Evaluated in-process in Rust (µs) instead of Celery (seconds).
- **Live layer (tick-to-tick)** — entry-zone touches, PDH/PDL/S&R breakout crosses, SL/TP proximity for open positions, volume bursts, provisional confidence on the forming candle (labeled "forming"), per-style leaderboard re-ranks. Batched 2–4 Hz; alerts instant via Redis Streams (at-least-once); LTP via pub/sub (fine to drop); frontend reconciles committed state over REST on reconnect. Backpressure: drop-oldest for LTP, never drop a candle-closing tick.

Session guard (no pre-open/post-close pollution), NSE holiday calendar, scheduled instrument-token re-sync/re-subscribe (F&O expiry churn), WS **auth** (currently the endpoint accepts anyone), a token-bucket Kite REST client (3 rps historical), batched warmup queries (4 per-TF queries, not 2000). Latency instrumented: tick → Redis publish p99 < 10 ms. A **tick record/replay harness is a mandatory deliverable** — there is no working baseline to diff against, so replay tests are the only ground truth.

### 3. Four style engines as data-driven "strategy profiles"

One confluence framework (hard constraint #4: never single-indicator signals), four seeded profiles with their own weights, timeframes, universe, validity, risk templates:

| Style | Core setups (masterclass + salvaged prototype concepts) | Timeframes |
|---|---|---|
| **Intraday** | DC1/DC2 double-confirmation; PDH/PDL breakout; opening-range breakout; 9:25 gainer/loser; 10 AM strategy | 5m/15m (+1h context) |
| **Swing** | RRBO (resistance breakout + 1.5× volume); pullback-to-demand-zone | 1d (+1h refinement) |
| **F&O** | Futures directional (underlying confluence + OI-confirmation factor); option-selling candidates (IV rank, PCR, max pain, regime gates → defined-risk structures with breakevens, margin estimate, POP) | per expiry |
| **Investment** | Multibagger EMA setup as primary; relative strength vs Nifty; FII/DII + sector alignment | 1d/1w |

New factors (PDH/PDL proximity, opening gap, relative strength, OI/ΔOI) enter *through* the confluence framework. Prototype math (25–40% confidence gates, single-indicator triggers) does not survive; your 70% gate does.

**F&O data before F&O analytics:** recorded history is the scarce resource. Two cheap recorders start in Phase 0 (~3–4 days): (a) **NSE F&O bhavcopy ingestion** (per-contract close/OI/volume, years of history → EOD IV → IV-rank/PCR/max-pain bootstrapped immediately, reusing the existing equity bhavcopy service pattern); (b) **intraday chain snapshots** via `kite.quote` REST (500 instruments/call at 1 rps — NIFTY/BANKNIFTY chains + stock futures fit a 1-minute Celery beat, no WS needed). India VIX as interim IV-regime proxy.

### 4. UI overhaul — antigravity design language on the existing token system

The 4-theme token system (midnight/carbon/ocean/daybreak), format lib, and tabular-nums discipline already shipped — so Phase 5 is an **IA + style-pages + option-chain + virtualization** job, not a re-theme:
- New sidebar IA with sections (Trade: Dashboard, Intraday, Swing, F&O, Investment, Live Signals · Research: Stocks, Screener, FII/DII, Filings, Strategy Lab · Manage: Positions, History, Journal, Portfolio · Admin: Users, Kite, Settings).
- New **"slate" theme** (prototype's #0f172a/#1e293b/#3b82f6) added as 5th theme, made default.
- Speed: TanStack Virtual (not yet installed) for live tables, rAF-batched WS application in `useLiveQuotes` v2 (also fix the hardcoded `ws://`), transient Zustand updates, route code-splitting. Perf budget written and measured; 60 fps under replayed full-rate ticks.

---

## Phase plan (v2) — realistic calendar: ~18–20 working weeks

Rule unchanged: one phase at a time, vertical slices, green tests + working demo + reviewed by the new subagents before the next.

### Phase 0 — Claude Code workbench, repo hygiene, triage, recorders (~1 week) ← executes on approval

1. **Git init first, before anything else** + `.gitignore` (.env/.secrets/node_modules/target/caches/uploads) + initial commit. An unversioned 12-phase codebase is the single largest current risk.
2. **Rebuild the venv** (non-snap `uv python install 3.12`), get the 453-test baseline green again; record results in CHANGELOG.
3. **Triage fixes** (small, load-bearing, each with a test): 100× sizing bug; Redis `SET ltp:{stock_id}` alongside publish; candle commit; `asyncio` thread bug + `TextClause` bug (minimal repair so the consumer *runs* — full replacement comes in Phase 3); signal dedup key; WS auth; Redis eviction split (broker keys out of LRU reach); backtest moved off the event loop (Celery task).
4. **`.claude/settings.json`** — permissions allow-list (make/pytest/uv/ruff/mypy/pnpm/cargo/git/docker compose/alembic), deny-list (.env/.secrets reads, rm -rf, DROP/TRUNCATE), hooks:
   - PostToolUse (Edit|Write): per-language auto-format+lint (ruff / prettier+eslint / cargo fmt) via one dispatch script.
   - PreToolUse (Bash): destructive-command guard. PreToolUse (Edit|Write): protected-file guard — `docs/SIGNAL_ENGINE.md` and applied migrations can't be silently edited.
5. **Subagents** (`.claude/agents/`), each with a strict output contract (findings table: severity, file:line, evidence, spec ref, fix, *how verified* — no speculation): `quant-verifier` (formula-by-formula vs SIGNAL_ENGINE.md, look-ahead/incomplete-candle/float-money hunting), `bug-hunter` (async/thread races, tz, boundaries, leaks), `ui-reviewer` (tokens, format.ts, portals, virtualization), `perf-auditor` (per-tick allocations, N+1, sync-in-async, Rust hot-path clones), `test-guardian` (tests-with-feature, hollow-assert detection).
6. **Rules** (`.claude/rules/`): python.md, typescript.md, rust.md, testing.md (NullPool + function-scoped loops, .com EmailStr, golden/replay patterns), trading-domain.md (no look-ahead, is_complete, confluence-only, sizing mandatory, paper default, circuit breaker, IST/UTC), ui.md. **Skills**: `/vertical-slice`, `/phase-gate`, `/signal-audit`, `/perf-bench`.
7. **Docs rewrite**: this plan lands verbatim as **`docs/UPGRADE_PLAN.md`** (committed first, so the "why" survives); **`docs/phases/`** directory started — one report per phase (`phase-00-workbench.md`, …) recording *goal → why → what was built → results/metrics → decisions taken*, written at each phase's close so future-you knows why every piece exists; CLAUDE.md (slim, current-truth — React 19/Vite 8/TS 6/Tailwind 4, real phase status, architecture map, pointers to rules/skills/agents), README.md, PHASES.md → v2 status tracker, ARCHITECTURE.md + PERFORMANCE.md skeletons, Rust section in TECH_STACK_RATIONALE.md; clean stale `.claude/settings.local.json`.
8. **F&O recorders start** (bhavcopy F&O + 1-min chain snapshots + India VIX) — so history accumulates while we build.

**Exit gate:** baseline green; hooks demonstrably fire; each agent returns its format on a sample diff; triage fixes tested; recorders writing real rows; docs coherent; git history exists.

### Phase 1 — Rust engine core + parity + benchmarks (3–4 weeks)

- rustup (user-level), workspace scaffold, maturin dev-build wired into uv venv; Make targets `engine-build/test/bench/parity`; CI-style `make check` extended with `cargo test`/`clippy`/`fmt`.
- **Adjudication checkpoint with you** (volume direction, RSI bands, SL canon, window canon, fill realism) → then freeze Python, export golden fixtures (real 2y candles from DB + per-factor outputs + edge cases).
- Implement engine-core mirroring the adjudicated spec; property tests + goldens in Rust; criterion benches; parity pytest behind `ENGINE_IMPL`.
- Benchmark table in docs/PERFORMANCE.md: full-universe scan, 2y/50-stock backtest, 200-combo grid — pandas vs Rust wall-clock.

**Exit gate:** tiered parity green; zero signal-decision diffs on 2y × Nifty50; existing analysis tests pass both modes; quant-verifier signs off factor-by-factor; benches published.

### Phase 2 — Strategy profiles: four style engines, offline (2 weeks)

- `strategy_profiles` table (versioned) + seeds; new factors (PDH/PDL, gap, relative strength; OI stub) with goldens; NSE holiday calendar + market calendar service (also fixes expiry: real trading days, real 3:15 PM); expiry sweeper actually scheduled.
- Per-style pipelines + `GET /api/v1/suggestions/{style}` (committed signals with factor breakdown), nightly + on-close.
- Walk-forward backtests per profile on ≥2y → per-profile regression goldens (>5% metric moves need explicit approval — existing rule, now enforced).
- End of phase: **Python factor code + flag deleted** per sunset policy (after shadow validation in Phase 3 if you prefer the extra caution — decided at the gate).

**Exit gate:** every profile has a documented backtest report (positive expectancy or flagged needs-tuning); suggestions API serving all four styles.

### Phase 3 — Realtime v2: tick-to-tick (3 weeks + 1-week market-hours soak overlapping Phase 4)

- Rebuild 1h table session-aligned (with SIGNAL_ENGINE §8 regression sign-off); live-worker process as designed above; LiveEngine warmup from DB (batched queries) + gap-fill wired in; session guard; token re-sync cycle; daily restart choreography.
- Tick triggers + provisional layer + leaderboards; Redis Streams for alerts; WS fanout by style/watchlist; throttling + backpressure policy.
- **Record/replay harness**: recorded tick sessions → deterministic engine outputs → CI replay tests; latency histograms (tick→publish p99 < 10 ms target).
- Signal-outcome tick evaluation (did entry zone touch before expiry?) built into the trigger set now — Phase 6 needs this data.
- One shadow week: Rust decisions vs frozen-Python double-check on closes; zero diffs required.

**Exit gate:** full-session soak stable (memory flat, zero dropped subscriptions, latency budget met); replay suite green in CI; committed-vs-forming semantics visible end-to-end.

### Phase 4 — F&O analytics (3 weeks)

- NFO universe sync + chain builder (±N strikes tracked live near ATM); recorded snapshots (running since Phase 0) + bhavcopy-derived EOD IV history → IV rank/percentile, PCR, max pain, basis.
- Rust options math (Black-Scholes/Black-76 IV Newton–Raphson, Greeks) validated against independent goldens.
- F&O suggestion engine v1: futures directional (confluence + OI confirmation), option-selling candidates (conservative defaults; **we calibrate your masterclass option rules together here**). Margin estimates via Kite margins API; forward-validation dashboard (POP vs realized) — stated honestly in the UI as forward-tested, not backtested.

**Exit gate:** chain API live through full sessions; options math goldens green; F&O suggestions flowing through confluence discipline.

### Phase 5 — UI overhaul (2–3 weeks)

- New IA + slate theme default; four style pages (virtualized live tables, committed vs forming separation, factor-breakdown drawer, one-click paper trade, per-style stats header); F&O page adds chain ladder (OI bars, IV, Greeks) + strategy cards; Live Signals → global feed + alert center (browser notifications); `useLiveQuotes` v2 (rAF batching, wss support, style subscriptions).
- Perf pass measured into docs/PERFORMANCE.md; 60 fps under replayed full-rate ticks.

**Exit gate:** ui-reviewer clean on every page; frontend tests updated; perf numbers recorded.

### Phase 6 — Suggestion outcome tracking + strategy lab v2 (2 weeks)

- Every committed suggestion auto-tracked to outcome (fills per anti-look-ahead rules; tick-level zone-touch data from Phase 3) → per-style hit rate, expectancy, factor-vs-outcome attribution dashboards.
- Strategy lab v2: Rayon grid/walk-forward tuning per profile; promotion workflow (tuned weights → new profile version, audit trail, regression gate).

**Exit gate:** ≥2 weeks of tracked suggestions in dashboards; one full tuning cycle documented.

### Phase 7 — Live-trading hardening (2 weeks + the 30-day paper gate)

- Kite order placement behind trading_mode + the **restarted** 30-day profitable-paper gate (clock starts when Phase 3 soaks clean, so it overlaps 4–6); kill switch; order reconciliation; static-IP runbook; VPS compose profile; backups; Timescale compression/retention policies + hypertable-DDL runbook.

**Exit gate:** semi-auto dry-run clean → 1-stock live pilot. Circuit breaker non-disableable, as always.

---

## Salvage map (antigravity prototype)

**Take:** menu concept → new IA; slate/blue theme; table density/status patterns; PDH/PDL/ORB concepts; realtime pipeline shape; request-prioritization/caching ideas. **Leave:** all signal math, security posture, test-free code. Nothing copied — concepts rewritten to spec with tests.

## Key risks

1. **Parity with pandas-ta 0.4.71b0 subtleties** (SMA-seeded EMA, RMA-based RSI, ADX construction, window canon) — mitigated by fixture-file oracle from the *frozen* Python, tiered tolerances, decision-parity gate.
2. **Kite constraints** — daily token expiry (drives the restart-not-reconnect design), 3 rps historical (token-bucket client), 3000 tokens/WS conn, F&O token churn (scheduled re-subscribe).
3. **Options history scarcity** — bhavcopy gives EOD depth; intraday chains are forward-recorded from Phase 0; option strategies are forward-validated and labeled as such.
4. **Corporate actions** — Kite history is split-adjusted, NSE bhavcopy raw is not; adopt a CA-detection + re-fetch policy in Phase 2 (documented in ARCHITECTURE.md).
5. **Hardware** — Rayon capped ~6 threads; per-stock streaming keeps grid searches inside 15 GB alongside Postgres/Redis/Vite.
6. **Paper-history reset** — sizing fix invalidates prior paper stats; the 30-day gate restarts (called out above, not buried).

## Zerodha API timeline (when you need to purchase)

- **Phases 0–2: no live Kite session needed.** Everything runs on the existing DB (5 yrs EOD), NSE public downloads (F&O bhavcopy, FII/DII, India VIX), unit tests, and replayed/synthetic ticks. The intraday chain-snapshot recorder gets *built* in Phase 0 but sits idle until a token exists.
- **Nice-to-have from Phase 2:** Kite **historical API** access to backfill intraday (5m/15m) candles so intraday/scalp profiles can be properly backtested — otherwise intraday profiles are validated forward in Phase 3 instead of historically.
- **Required at Phase 3 start (Realtime v2):** active Kite Connect subscription — live WebSocket is the whole phase. I'll flag this explicitly at the Phase 2 → 3 boundary so you can purchase then. Daily token refresh (expires ~6 AM IST) is part of the Phase 3 design.

## On loss minimization

You're right, and it's the correct framing: profits can't be promised, but losses are controlled by construction — mandatory position sizing off SL distance, max-SL rejection rules, classification-correct validity windows, the non-disableable daily circuit breaker, trail-to-breakeven state machine, and (new in Phase 6) outcome attribution that tells us *which setups actually lose* so they get tuned or cut. That machinery is exactly what this plan hardens.

## Verification (every phase)

`make check` (pytest + ruff + mypy + vitest + eslint + tsc, plus cargo test/clippy from Phase 1) · parity + backtest-regression gates · replay harness from Phase 3 · manual smoke demo per the existing definition of done · quant-verifier + bug-hunter subagent review on every substantive diff.

## On approval (auto mode)

I execute **Phase 0 completely and autonomously**: commit this plan as `docs/UPGRADE_PLAN.md` → git init → venv rebuild → baseline → triage fixes with tests → workbench (hooks/agents/rules/skills) → docs rewrite → recorders → write `docs/phases/phase-00-workbench.md` with results. Phase 1 then kicks off explicitly. Every phase ends with its report file so the why-and-what is permanently documented.
