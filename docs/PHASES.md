# 12-Phase Build Plan

Each phase is a vertical slice: backend + frontend + tests built together so every phase ends with something demonstrable. **Do not start phase N+1 until phase N has green tests and a working demo.**

| # | Phase | Calendar | Demo at end |
|---|---|---|---|
| 0 | Infrastructure foundation | 3 days | `make up` brings up Postgres+TimescaleDB+Redis; `make db-extensions` confirms TimescaleDB loaded. **← already done** |
| 1 | Auth & user master | 1 week | Login screen → JWT issued → protected route returns user profile. Admin user can create new users. No public signup. |
| 2 | Stock master + advanced screener | 1.5 weeks | Nifty50 + BankNifty + F&O stocks loaded. Searchable table. **aftermarkets-style 50+ filter screener with save/load named screens.** |
| 3 | Categories master | 4 days | Tag stocks with categories (pharma, EV, defence). Filter by category combined with screener. |
| 4 | EOD ingestion + FII/DII flows | 1.5 weeks | 5 years daily OHLCV for Nifty50 stocks. **Daily FII/DII data ingested from NSE. Bulk/block deals from BSE/NSE.** Candlestick chart renders on stock detail. |
| 5 | **Signal engine (offline)** | 3 weeks | All 15 patterns + 10 indicators + S&R + Fibonacci + Dow + institutional flow factor implemented. Confluence scorer with 10+ factors. Backtest harness reports win rate, Sharpe, max drawdown on 2 years of Nifty50 data. **Decision gate: positive expectancy required before continuing.** |
| 6 | Dashboard v1 + corporate filings feed | 2.5 weeks | Sortable signal list with confidence %, classification, entry/SL/TP, suggested qty. Factor breakdown bar chart on click. **Live corporate filings feed from NSE/BSE. Event guard suppresses signals during filings.** Daily FII/DII summary card. |
| 7 | Live data via Kite WebSocket | 2 weeks | Tick consumer → 5m/15m/1h candle aggregation → signal regeneration → frontend WebSocket push. Reconnection + gap-fill logic. |
| 8 | Paper trading | 2 weeks | "Buy on signal" → virtual order → simulated fill → position tracked → exit on SL/TP. P&L summary. **Daily-loss circuit breaker active.** **Run ≥ 30 days here before Phase 12.** |
| 9 | Strategy lab | 2 weeks | Backtest UI: select date range + factor weights + stocks → win rate / Sharpe / drawdown table with ranked combinations. "Best strategy for last week/month/year/custom range" answered. Sentiment scoring (FinBERT) for filings added here as optional factor. |
| 10 | Trading journal | 1 week | Auto-populated from paper trades. Manual notes, screenshots, emotion-before/after tags, lesson-learned field. Full-text search. |
| 11 | External portfolio | 2 weeks | CAMS CAS PDF import for MF holdings. Manual entry forms for gold, SIPs, FDs. Consolidated net-worth dashboard across stocks + MFs + gold. |
| 12 | Live trading via Kite | 2 weeks | Switch paper → live, one stock at a time. Hard daily-loss limit. Kill-switch button. Static IP setup required (see README). |

**Total ~15 weeks personal pace.** Phases 1–8 are critical path; everything else can be deferred without losing core value.

---

## Decision gates

Hard stops where we evaluate before continuing:

- **End of Phase 5** — does backtest show positive expectancy on 2 years of Nifty50?
  - YES → proceed to Phase 6
  - NO → tune factor weights, revisit indicator math, possibly question entire approach. Do not build UI on a broken engine.
- **End of Phase 8** — does paper trading show profit over 30 days *with discipline* (no manual overrides)?
  - YES → proceed toward Phase 12 (after journal + portfolio + strategy lab)
  - NO → do NOT enable live trading. Investigate which signals fail and why; iterate.
- **End of Phase 11** — do you intend to rent out modules to others?
  - YES → pause, evaluate SEBI Research Analyst registration; add multi-tenancy, billing, rate-limiting
  - NO → straight to Phase 12 for personal use

---

## Per-phase detail

### Phase 0 — Infrastructure ✓
Done. Files: `docker-compose.yml`, `Makefile`, `.env.example`, init scripts.

### Phase 1 — Auth & user master
- Backend: SQLAlchemy `User` model, bcrypt hashing, JWT (access 15min, refresh 7d httpOnly cookie), `/auth/login`, `/auth/refresh`, `/auth/logout`, admin-only `/users/` CRUD
- Frontend: login page, protected route wrapper, admin user-management page
- Tests: auth flow integration, token rotation, admin-permission enforcement
- Migration: users + user_sessions tables (see `DATABASE_SCHEMA.sql`)

### Phase 2 — Stock master + screener
- Backend: `Stock` model, ingest seed Nifty50/BankNifty/FNO list from NSE CSVs, `/stocks` list+search+filter, `/screener/run` endpoint with filter spec compiler
- Frontend: stock list table with search/sort, screener filter builder, saved screens
- Tests: filter spec → SQL compilation correctness, edge cases (empty filters, invalid ops)

### Phase 3 — Categories
- Backend: `Category` model, many-to-many join table, CRUD endpoints, screener integration
- Frontend: category master page, tag picker on stock detail, category filter
- Tests: many-to-many integrity, soft-delete cascade

### Phase 4 — EOD + FII/DII
- Backend: bhavcopy downloader + parser (NSE daily 5pm IST), FII/DII daily fetcher, bulk/block deals fetcher, hypertable inserts
- Frontend: candlestick chart (Lightweight Charts) on stock detail, FII/DII trend chart
- Tests: bhavcopy parser handles edge cases (holidays, file format changes), idempotent re-imports
- Backfill: 5 years of daily OHLCV for ~200 stocks (Nifty50 + extended F&O list)

### Phase 5 — Signal engine (offline)
**3 weeks — the most important phase.** See `SIGNAL_ENGINE.md` for full spec.
- Week 1: All patterns (single + multi) with golden-value tests
- Week 2: All indicators (RSI, MACD, EMA, ADX, BBands, ATR) + S&R + Fib + Dow trend
- Week 3: Confluence scorer + risk sizer + classifier + backtest harness on 2 years Nifty50
- **Decision gate before Phase 6.**

### Phase 6 — Dashboard + filings feed
- Backend: nightly signal generation job (Celery beat at 6 PM IST), `/signals/active` endpoint, corporate filings ingestion + event guard
- Frontend: dashboard with signal list table, signal detail modal (factor breakdown), candlestick chart with markers, P&L summary cards, live filings panel
- Tests: signal expiry, factor breakdown rendering, filing event guard suppression

### Phase 7 — Live Kite WebSocket
- Backend: Kite WebSocket client, tick → candle aggregator, Redis pub/sub fan-out, FastAPI WebSocket endpoint
- Frontend: live LTP tickers, real-time candle updates, signal push via WS
- Tests: reconnection logic, gap-fill on disconnect, ordered tick processing

### Phase 8 — Paper trading
- Backend: paper broker (simulates fills at next-tick price), position lifecycle, P&L computation, daily-loss circuit breaker (forces "no new signals" if hit)
- Frontend: "paper buy/sell" buttons on signals, positions page, trade history, daily P&L
- Tests: position open/close/partial close, trail SL state machine, circuit breaker triggers

### Phase 9 — Strategy lab
- Backend: backtest engine using vectorbt or own implementation, factor weight grid search, results storage, sentiment scoring add-on
- Frontend: backtest config form, results comparison table with rankings, equity curve charts
- Tests: backtest determinism (same inputs → same outputs), look-ahead bias prevention

### Phase 10 — Journal
- Backend: journal CRUD, auto-populate from closed positions, screenshot upload to local FS / S3
- Frontend: journal entry form, journal list with search, emotion tag analytics
- Tests: search full-text, screenshot upload size limits

### Phase 11 — External portfolio
- Backend: CAMS CAS PDF parser (use `pdfplumber`), manual entry endpoints, net-worth aggregator
- Frontend: CAS upload flow, asset entry forms, consolidated net-worth dashboard
- Tests: PDF parsing on multiple CAS format versions

### Phase 12 — Live trading
- Backend: Kite order placement, fill reconciliation, hard daily-loss limit, kill switch
- Frontend: mode switch (paper ↔ semi-auto ↔ live) with confirmation, live position panel
- Tests: order placement error handling, fill mismatch reconciliation, kill switch atomicity
- **Requires static IP setup before live mode activates** (see README)

---

## What we are NOT building (yet)

These were considered and consciously deferred:

- **Mobile native app** — web app will be mobile-responsive; native only if commercialized
- **Options trading strategies** — masterclass Classes 8/9/10 cover this richly, but options need Greeks + IV modeling — adds Phase 13 if equity proves out
- **Account Aggregator (Finvu/Setu)** for portfolio sync — proper FIU registration is bureaucratic; CSV imports cover the same ground for v1
- **AI/ML signal generation** — only after Phase 9 proves rule-based engine works. ML on a broken engine just learns the bugs.
- **Multi-user / SaaS infrastructure** — multi-tenancy, billing, rate-limiting, SOC2 — deferred until rent-out decision is made
- **Indian commodity markets (MCX)** — masterclass mentions but out of scope for v1
