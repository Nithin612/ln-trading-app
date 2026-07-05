# Architecture

> Skeleton created in v2 Phase 0. Sections marked *(Phase N)* are filled in
> when that phase lands — this file is the living map, UPGRADE_PLAN.md is
> the frozen rationale.

## System overview (current, post-Phase-0)

```
┌─ External ────────────────────────────────────────────────────────────┐
│ Kite WS (ticks) · Kite REST (quote/historical/instruments)            │
│ NSE archives: equity bhavcopy · F&O bhavcopy (UDiFF) · indices/VIX ·  │
│ FII/DII · corporate filings                                           │
└──────────────┬────────────────────────────────────────────────────────┘
               ▼
┌─ Ingestion ───────────────────────────────────────────────────────────┐
│ TickConsumer (KiteTicker thread → asyncio queue → batch loop):        │
│   candles 1m/5m/15m/1h → Postgres · SET ltp:{sid} + pub/sub → Redis   │
│ Celery beat: EOD bhavcopies · FII/DII · filings 60s · F&O bhavcopy    │
│   18:45 IST · India VIX · chain snapshots 1-min (needs Kite token)    │
└──────────────┬────────────────────────────────────────────────────────┘
               ▼
┌─ Compute ─────────────────────────────────────────────────────────────┐
│ Python analysis/ : 14-factor confluence engine (≥70% gate), risk      │
│   sizer, classifier, expiry — FROZEN at Phase-1 parity, then replaced │
│   by Rust engine-core (tradecore wheel)             (Phase 1)         │
│ Backtest harness (anti-look-ahead)  → Rust Rayon    (Phase 1/6)       │
│ LiveEngine: per-tick provisional layer + candle-close committed       │
│   signals in-process                                (Phase 3)         │
│ Options math: BS/Black-76 IV, Greeks, IV-rank/PCR/max-pain (Phase 4)  │
└──────────────┬────────────────────────────────────────────────────────┘
               ▼
┌─ Storage ─────────────────────────────────────────────────────────────┐
│ Postgres 16 + Timescale (5433): ohlcv_{1m,5m,15m,1h,1d} hypertables · │
│ fo_bhavcopy · india_vix_daily · option_chain_snapshots (7d chunks) ·  │
│ signals/outcomes · orders/positions · everything relational           │
│ Redis 7 (volatile-lru): ltp:{stock_id} keys (TTL 600s) · pub/sub      │
│ channels ltp:{token}, candle:{table}:{sid} · Celery broker (no-TTL    │
│ keys = never evicted) · Streams for alerts          (Phase 3)         │
└──────────────┬────────────────────────────────────────────────────────┘
               ▼
┌─ Presentation ────────────────────────────────────────────────────────┐
│ FastAPI /api/v1/* (JWT) · /ws/live (JWT on upgrade, keepalive-anchored│
│ pubsub reader) · React 19 SPA: token-driven 5-theme UI                │
│ Style pages Intraday/Swing/F&O/Investment            (Phase 5)        │
└───────────────────────────────────────────────────────────────────────┘
```

## Load-bearing contracts

| Contract | Producer | Consumer | Shape |
|---|---|---|---|
| `ltp:{stock_id}` Redis KEY (TTL 600s) | tick consumer | paper broker fills/SL-TP | Decimal-parseable string; constant `LTP_KEY` in `app/broker/tick_consumer.py` — import, never retype |
| `ltp:{instrument_token}` channel | tick consumer | /ws/live fanout | JSON `{instrument_token, stock_id, ltp, ts}` |
| `candle:{table}:{stock_id}` channel | tick consumer | /ws/live fanout | full candle JSON + `is_complete` |
| Celery `live_signal_generation` | tick consumer (post-commit, off-loop) | worker | fired only AFTER candle commit |
| WS close code **4401** | /ws/live | frontend `useLiveQuotes` | auth failure — client must NOT auto-reconnect |

## Adjudicated canon (2026-07-04 — user decisions with measured evidence)

Five spec-drift questions were measured on 2y × 49 Nifty50 real data
(scripts/adjudication_experiments.py) and decided:

| # | Decision | Evidence (vs as-is baseline 863tr/39.8%/+1.8pnl/−0.07sh) |
|---|---|---|
| A | Volume counts only WITH the confluence direction (scorer-level flip/zero) | alone: +41.6 totPnL, sharpe +0.07 |
| B | RSI ±0.4 bands at <30/>70 removed (off-spec) | neutral (+3.3) |
| C | ONE swing-SL implementation: pivot N=5 (dow.swing_levels) for live AND backtest; degenerate/wrong-side SLs rejected | alone: +44.2, sharpe +0.10, fewer trades |
| D | Committed signals see exactly the last ≤300 completed candles, everywhere | growing≈300: 99.7% agree, 0 direction flips |
| E | HONEST fills: gap-through exits at open; fill candle checked intrabar; SL before TP | reveals as-is strategy at −109 totPnL — the old +1.8 was fill flattery |

Consequence accepted with eyes open: the truthful baseline on 2023–26 daily
data is NEGATIVE (A+B+C+E ≈ −108 totPnL). Profitability is Phase-2
(profiles) + Phase-6 (tuning) work, now measured against reality. Guarded
by tests/analysis/test_adjudicated_semantics.py on the Python side and the
regenerated oracle fixtures on the Rust side.

**Second round (2026-07-05 — Phase-1 exit-gate findings, measured by
scripts/adjudication_experiments_fgh.py on the pinned 2y × 49 corpus;
baseline reproduced the 807-trade parity oracle exactly before ruling):**

| # | Decision | Evidence |
|---|---|---|
| F | IMPLEMENT §4: ATR(14) > 3% of price → qty reduced 25% (`3·q // 4`, strict `>`; reduction to 0 rejects; ATR computed on the decision window, never the fill candle) | 46/807 trades were volatile-regime and net WINNERS: costs ₹37,195 P&L for ₹1,15,481 less capital-at-risk — accepted knowingly as a risk rule, not an alpha rule |
| G | IMPLEMENT §2.2: star's real body must gap fully beyond the first candle's body (strict inequalities) | 78% of old star detections were gap-false; corpus flips 807→599 trades, totPnL −78.7 → +52.1, sharpe −0.27 → +0.13 |
| H | KEEP per-sub-factor weights; SIGNAL_ENGINE.md §3/§7 amended to match code (BBANDS 10 row added; §7 regenerated from live output — POWERGRID conf 75) | sharing group weights loosened the gate: 1,212 trades, totPnL −744.4, sharpe −1.10 — per-sub-factor dilution IS the conservative filter |

New standing baseline (post F+G, same corpus): **599 trades · win% 40.1 ·
totPnL +52.1 · sharpe +0.13 · maxDD 96.2** — first positive corpus
baseline; Rust engine-cli reproduces the 599 exactly (172 ms). Oracle
fixtures regenerated in the same commit via the new
scripts/generate_engine_fixtures.py (backtest oracle 125→101 trades).
Guarded by TestStarGapRequired / TestVolatilitySizing in
tests/analysis/test_adjudicated_semantics.py.

## Semantics that must never drift silently

- Candle timestamps: kiteconnect delivers **naive host-local** datetimes in
  `exchange_timestamp` → `astimezone(UTC)` (never `replace`). Candle volume
  = diff of cumulative `volume_traded` (never sum of snapshot quantities).
- Committed signals: last-300-completed-candles window, `is_complete=true`
  only, idempotent per (stock, timeframe, direction) while active.
- Known debt, scheduled: 1h candles are UTC-hour floored (9:30-IST anchored)
  while Kite's 60minute history is 9:15-anchored — same table, two time
  bases. **Rebuild session-aligned in Phase 3** with spec §8 sign-off.
- Corporate actions: Kite history is split-adjusted; NSE bhavcopy raw is
  not. Adjustment policy lands in Phase 2 — until then do not mix sources
  within one indicator window.

## Process model *(Phase 3 fills this in)*

Target: FastAPI (API + WS fanout) · live-worker (KiteTicker + Rust
LiveEngine; daily restart at token expiry, warmup from DB + gap-fill) ·
Celery worker + beat · Postgres · Redis. Tick path: ticker thread →
`queue.Queue` → consumer thread → ONE PyO3 call per batch → sync redis
pipeline. Backpressure: drop-oldest LTP, never a candle-closing tick.

## Engine workspace *(Phase 1 fills this in)*

engine-core (pure, no I/O, no clocks) · engine-py (tradecore, GIL released
around compute, batch calls) · engine-cli (replay/bench). Parity canon and
numeric conventions: `.claude/rules/rust.md`. Golden fixtures under
`engine/crates/engine-core/tests/fixtures/` (pandas-ta version recorded
inside); the cross-language pytest side lives in `backend/tests/parity/`.
