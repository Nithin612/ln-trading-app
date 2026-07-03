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
`backend/tests/fixtures/engine/` (pandas-ta version recorded inside).
