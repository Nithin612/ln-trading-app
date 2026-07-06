# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### v2 Phase 2 — Strategy profiles (in progress, started 2026-07-05)

- **Fixed a 100×-family sizing hazard on `POST /signals/generate`**: the admin endpoint defaulted `risk_pct=0.02` (fractional style) in a whole-percent convention — a default request risked 0.02% instead of 2%. Default is now 2.0 with a [0.1, 10] validation floor that rejects fractional-style values loudly (+3 regression tests)
- **NSE market calendar** (slice 1): `nse_holidays` table + `market_calendar` service (`is_trading_day`, `add_trading_days`, `last_n_trading_days`, `validity_offset_days`) + admin CRUD at `/api/v1/calendar/*`. Seeded with **46 holidays derived from bhavcopy session gaps** (2023-07→2026-07 — data is the authority for the past) + published future dates; the service warns when queried beyond coverage. Swing/positional signal validity now uses **real trading days** (5/30) instead of the 7/42 calendar-day approximation — a Diwali-week swing signal now correctly lives to the 5th session. Nightly generation, F&O EOD ingestion, and the chain recorder skip market holidays (+15 tests)
- **Signal expiry sweeper** (slice 2): spec §5's "runs every 5 minutes" sweeper now exists — lapsed active signals flip to `expired` + `expired_at` on the beat; previously NOTHING ever wrote expiry status (lazy query-filter only). Injected session/clock core, 3 tests
- **FII/DII flows finally reach signal generation** (slice 3): `get_market_flow_5d` (cash segment, last 5 TRADING days via the calendar) + `get_stock_block_deal_net_cr` wired into nightly, live, and admin generation — the ±5-weight §2.7 factor had scored zero on every signal ever generated. FII/DII ingestion is now on the beat (18:30 IST; was manual-POST only). +5 tests
- **EOD pipeline ordering fixed** (slice 3): there was NO daily equities-EOD ingestion task at all (`ohlcv_1d` only ever written by the Phase-1 backfill script) — nightly generation scored stale candles. New `ingest_equities_eod` beat task (18:40 IST) + nightly generation moved 18:00 → **19:15 IST** so it consumes same-day candles and flows
- **Setup evaluators + seed profiles** (slice 5): `app/profiles/setups.py` — nine pure, direction-aware evaluators (`pdh_breakout` PDH/PDL momentum, `pdl_breakdown`, `opening_gap`, `relative_strength` vs NIFTY50, `dc1` (SR_ZONE sugar), `dc2` (prior-candle DC1 + confirmation), `orb_breakout`, `top_gainer_925`, `factor_score`) shared verbatim between the live pipeline and the walk-forward runner; fail closed on missing context; AND-combined with evidence persisted to `setup_trigger`. Import-time registry↔schema sync guard. Seed migration `o1p2q3r4s5t6`: 8 profiles with frozen config literals + hashes (dc1/dc2/rrbo_basic/rrbo_trailing/multibagger active; pdh_pdl/orb_15m/gainer_925 defined-but-inactive until Phase 3), seed-integrity test re-validates literals against the live schema. +24 tests
- **`strategy_profiles` schema** (slice 4): versioned, immutable profile rows (edits insert `(key, version+1)` and supersede — a DB partial-unique index enforces one live row per key); typed JSONB shapes (universe/setups/risk-template/validity discriminated unions, reject-don't-clamp) with `config_hash` for golden drift-detection; `min_confidence ≥ 70` CHECK — profiles may raise the gate, never lower it. `signals` gains `profile_id` (exact version, DELETE-RESTRICT) / `profile_key` / `setup_trigger` / `volatility_reduced` (§4 attribution now written by both generation paths) + a partial-unique index = DB-enforced one-active-suggestion-per-(stock, profile). Universe resolution lifted to `services/universe_service.py` (+ category-slug universes); strategy-lab API delegates. Reversible migration `n0p1q2r3s4t5`, +15 tests

### Adjudications F/G/H — star gap, volatility sizing, weight semantics (2026-07-05)

User rulings on the three spec-vs-code drifts found at the Phase-1 exit gate, applied per SIGNAL_ENGINE.md §8 (both engines in lockstep, oracles regenerated in the same commit; evidence: `scripts/adjudication_experiments_fgh.py`, table in the phase-01 report §Exit gate):

- **G — implemented in both engines**: Morning/Evening Star now require the star's real body to gap fully beyond the first candle's body (§2.2). 78% of previous detections were gap-false and their ±0.95 dominated best-pattern selection; the pinned 2y×49 corpus flips 807→599 trades, totPnL −78.7% → **+52.1%**, sharpe −0.27 → +0.13
- **F — implemented in both engines**: ATR(14) > 3% of price on the decision window → quantity reduced 25% (`volatility_adjusted_qty` / `volatility_reduced_qty`, exact `3·q // 4` integer arithmetic both sides; reduction to zero rejects). Applied in the backtest engine and BOTH live signal_service call sites
- **H — code semantics kept, spec amended**: per-sub-factor weights are canon (max applicable weight 150 + 10 multibagger). SIGNAL_ENGINE.md §3 table rewritten to match the code (+ Bollinger Bands 10 row + semantics note); §7 worked example regenerated from real engine output (POWERGRID, conf 75 — the old TATAMOTORS example never reconciled). Protected-spec guard lifted for exactly two edits on explicit user instruction, restored byte-identical
- **Fixture regeneration is now repeatable**: new `scripts/generate_engine_fixtures.py` recomputes all Python-oracle fixtures from the live engine while keeping the committed bars verbatim (backtest oracle 125→101 trades; 3 confluence windows re-scored; analysis fixture unchanged). Rust reproduces all three exactly
- **New standing baseline** (pinned corpus, anchor 2024-06-04): **599 trades · win% 40.1 · totPnL +52.1% · sharpe +0.13 · maxDD 96.2%** — the first positive corpus baseline; Rust `engine-cli` reproduces 599 in 172 ms. Star detections drop 1,778 → 394
- Tests: backend 453→**461** (8 new adjudication regressions) · Rust 30→**33** · parity 6 · quant-verifier signoff

### v2 Phase 1 — Rust engine core, adjudication, parity, 6,180× (2026-07-04)

Full report: `docs/phases/phase-01-rust-engine.md`.

- **3y EOD backfill** (ohlcv_1d was EMPTY despite v1 claims): 1.29M candles, 2,330 stocks + `scripts/backfill_eod.py`
- **engine/ Rust workspace** (rustc 1.96.1): engine-core (indicators/patterns/structure/factors/confluence/risk/backtest — incremental state + batch on top), engine-py → `tradecore` (PyO3 abi3), engine-cli (bench)
- **pandas-ta 0.4.71b0 semantics decoded** (SMA-seeded EMA, first-diff-seeded RSI, prenan ADX with first-DX seed, ddof=1 BBands) and locked by committed reference fixtures — machine-precision parity (≤1e-12 real-data error)
- **Five spec drifts adjudicated by the user with measured evidence** (see ARCHITECTURE.md): volume direction-match · RSI bands removed · pivot swing-SL shared live+backtest · last-300 window canon · HONEST fills (which revealed the old +1.8% totPnL as fill flattery — truthful baseline ≈ −108%; tuning is Phase 2/6 against reality). Applied to BOTH engines in lockstep + 8 regression tests
- **Cross-language parity suite** (`make parity`): exact factor scores/confidence/decisions on 96 real windows; exact 125-trade backtest lists; ENGINE_IMPL flag (python|rust) wired through signal_service with dispatch tests
- **Benchmark** (docs/PERFORMANCE.md): 2y×49 full backtest **883.8 s → 0.143 s (~6,180×, RAYON=6)**; 200-combo grid ≈50.5 h → ≈29 s
- Python engine frozen (bugfix-only; sunset after Phase-3 shadow week)
- **Exit gate passed 2026-07-05** (`/phase-gate`): full `make check` green — Rust 30 · backend 453 · frontend 131 · parity 6; quant-verifier signoff (adjudicated canon in both engines, look-ahead hygiene, money discipline, exact parity). Gate fixes: missed rustfmt pass committed (+ `backtest` added to the engine-cli usage hint); `ENGINE_IMPL=rust` dispatch now fails loud on FII/DII flows and answers off-1d timeframes with the python engine — only 1d is fixture-pinned (+2 regression tests); `parity` pytest mark registered; smoke reproduced the recorded bench to the trade (807 on the bench-day corpus). Three pre-existing spec-vs-code drifts recorded for user adjudication (§4 ATR>3% sizing · §2.2 star gap condition · sub-factor weight semantics) — see phase report §Exit gate


### v2 Phase 0 — Claude workbench, repo hygiene, triage, F&O recorders (2026-07-03)

The first phase of the approved v2 upgrade (`docs/UPGRADE_PLAN.md`). Full
report: `docs/phases/phase-00-workbench.md`.

#### Repo & tooling
- **Git initialized** (the 12-phase codebase was unversioned); pristine baseline commit, `.gitignore` hardened (fixed `lib/` pattern that would have ignored `frontend/src/lib/`)
- **Backend venv rebuilt** on a snap-proof Python 3.12 (previous interpreter was garbage-collected by a snap refresh — tests could not run)
- **Claude Code workbench**: `.claude/settings.json` permissions + 3 hooks (auto-format per language; destructive-command guard, 12 cases verified; protected-file guard for SIGNAL_ENGINE.md/applied migrations/.env, 7 cases verified) · 5 review agents with strict evidence contracts (quant-verifier, bug-hunter, ui-reviewer, perf-auditor, test-guardian) · 6 rules files · 4 skills (/vertical-slice, /phase-gate, /signal-audit, /perf-bench)
- **Ruff + mypy brought to zero** across the backend (48 + 18 baseline findings)

#### Critical fixes (each with regression tests)
- **100× position undersizing**: signal_tasks pre-divided risk% by 100 and compute_quantity divided again — every system-generated signal risked 0.02% instead of 2%. **Paper-trading history before this fix is invalid; the 30-day gate restarts.**
- **Live tick pipeline repaired** (it had never worked end-to-end): asyncio.get_event_loop on the KiteTicker thread (RuntimeError on 3.12); .format() on a TextClause (AttributeError on first candle); flush-without-commit (candles invisible all day); LTP published to a channel but never SET as the key paper_broker reads (intraday SL/TP silently ran on stale EOD closes)
- **From bug-hunter agent review** (3 confirmed by reproduction): batch failures no longer kill the tick loop (one Redis blip used to end live data for the day; task now supervised + loud); candle timestamps converted with astimezone (kiteconnect sends naive HOST-LOCAL datetimes in `exchange_timestamp` — every live candle was mislabelled +5:30 on an IST host); /ws/live pubsub reader anchored with a keepalive subscription (redis-py listen() exits on an unsubscribed pubsub — the stream was dead on arrival); candle volume now diffs cumulative `volume_traded` (snapshot-quantity summing fed garbage to the volume factor); Celery publishes batched off the event loop; `asyncio.run` replaces `get_event_loop().run_until_complete` in all Celery tasks
- **Signal idempotency**: active-signal dedup guard — candle-close regeneration no longer mints near-duplicate signals every period
- **/ws/live authenticates**: JWT required on the upgrade (close code 4401; refresh tokens rejected); useLiveQuotes sends the token, supports wss, stops reconnect-looping on auth failure
- **Redis eviction**: allkeys-lru → volatile-lru so Celery broker keys can never be silently evicted; stale container recreated (it predated the port mapping)
- **Backtests off the event loop** (asyncio.to_thread) — running a backtest no longer freezes the API and live WebSocket

#### F&O data recorders (recording starts now; analytics consume it in Phase 4)
- `fo_bhavcopy` — NSE UDiFF derivatives EOD (futures+options close/settle/OI/volume), idempotent, Celery beat 18:45 IST
- `india_vix_daily` — VIX EOD from the NSE indices bhavcopy (interim IV-regime proxy)
- `option_chain_snapshots` (Timescale hypertable) — 1-minute nearest-expiry chain snapshots via kite.quote for NIFTY/BANKNIFTY (2N+1 strikes around spot); idles without a Kite token
- `kite_instruments`: NFO segment synced with strikes; tokens widened to BIGINT; migration `k7l8m9n0p1q2` verified reversible

#### Docs
- Approved plan committed as `docs/UPGRADE_PLAN.md`; `docs/phases/` reports started; CLAUDE.md/README/PHASES rewritten to current truth; ARCHITECTURE.md + PERFORMANCE.md started; Rust rationale added to TECH_STACK_RATIONALE.md; CLAUDE_CODE_GUIDE.md updated for the workbench

#### Tests
- **+45 backend tests** (sizing 3, tick consumer 7 + loop survival 1, dedup 5, WS auth 9, aggregator regressions 4 + fixture truth-up, F&O recorders 16) — backend total 439, frontend 131

### UI Polish v2 — pre-Phase-12 sprint

#### Frontend
- **4-theme design system** (`src/styles/tokens.css`) — full CSS token rewrite; four named themes (midnight/carbon/ocean/daybreak) replacing the old dark/light binary; backward-compat mappings for old localStorage values; new tokens: `--color-border-strong`, `--color-warning-bg`, `--color-info-bg`, `--color-accent-bg`, `--font-ui`, `--font-num`
- **Theme switcher** (`src/pages/admin/SettingsPage.tsx`) — 2×2 card grid replacing the old radio list; each card shows bg swatch + accent dot + active badge; daybreak (light) card correctly previews light surface
- **Continuous font size** — slider (12–22 px, step 1) + five preset chips (Compact/Default/Comfortable/Large/X-Large) writing `--ui-font-size` CSS variable; replaces the old three-state discrete toggle
- **Split font system** — separate UI font selector (Inter/Geist/IBM Plex Sans/Roboto) and numeric font selector (JetBrains Mono/IBM Plex Mono/Roboto Mono/Inter tabular) stored in `uiPrefsStore`; applied via `data-ui-font` and `data-num-font` attributes on `<html>`
- **Profile dropdown** (`src/components/ui/profile-dropdown.tsx`) — ported to `createPortal` + `getBoundingClientRect` so it escapes `overflow: hidden` clipping; solid `--color-surface` background (no semi-transparent bleed)
- **Login page redesign** (`src/pages/LoginPage.tsx`) — glow-orb + subtle grid background layer; brand logo + monospace heading + tagline; shadcn `Input` for email; new `PasswordInput` component for password
- **PasswordInput component** (`src/components/ui/PasswordInput.tsx`) — show/hide toggle with Eye/EyeOff icons; aria-label `Show characters` / `Hide characters` avoids collision with `getByLabelText(/password/i)` in tests
- **KpiCard component** (`src/components/ui/KpiCard.tsx`) — card with 4 px left accent border, value in tabular-nums mono, optional sub-line with trend coloring; supports profit/loss/warning/info/accent variants
- **Action icon colors** — delete/trash hover color unified to `--color-loss` (was `--color-bear` in JournalPage)
- **Market status chip** (AppShell) — raw `text-green-400`/`bg-green-900` replaced with `--color-profit-bg`/`--color-profit`; yellow PRE-MARKET uses `--color-warning-bg`/`--color-warning`
- **Native `<select>` elimination** — replaced in `Pagination` (page-size picker), `UsersPage` (role and trading_mode), previously `DashboardPage`, `FilingsPage`, `TagPicker`; all now use `SimpleSelect` backed by base-ui portal
- **`themeStore`** — extended with `carbon` and `ocean` themes, `setTheme()` action, backward-compat toggle (daybreak ↔ midnight); old `'dark'`/`'light'` localStorage values auto-migrated
- **`uiPrefsStore`** — extended with `fontSizePx`, `uiFont`, `numFont` state and setters; `setFontSizePx` writes `--ui-font-size` inline; boot hydration in `main.tsx`
- **Select popup styling** (`src/components/ui/select.tsx`) — replaced shadcn defaults with `--color-surface`/`--color-border-strong` tokens; no semi-transparent backgrounds

### Phase 11 — External Portfolio

#### Backend
- **Alembic migration** `j1k2l3m4n5o6` — creates `mf_import_batches`, `mf_holdings`, `manual_assets` tables with UUID PKs, BigInteger FKs to users, and covering indexes; fully reversible
- **ORM models** (`app/models/portfolio.py`) — `MfImportBatch` (source PDF metadata, totals), `MfHolding` (amc, scheme, folio, isin, units/NAV/value as Numeric), `ManualAsset` (gold/FD/PPF/NPS/bonds/real_estate/other with cost basis and maturity fields)
- **CAS PDF parser** (`app/services/cas_parser.py`) — state-machine parser for CAMS Consolidated Account Statement PDFs via `pdfplumber`; extracts header (investor name, PAN, statement date) and holdings (AMC, scheme, folio, ISIN, units, NAV, current value, valuation date); flush-when-complete design avoids look-ahead bias
- **Portfolio service** (`app/services/portfolio_service.py`) — `import_cas_pdf` (parse + upsert batch + holdings in one transaction), `get_batch_with_holdings` (selectinload), `get_net_worth` (aggregates equity open positions + latest MF batch + manual assets into `NetWorthOut`)
- **Portfolio API** (`app/api/v1/portfolio.py`) — `POST /portfolio/cas/upload` (20 MB limit, PDF-only), `GET /portfolio/cas/batches`, `GET /portfolio/cas/batches/{id}`, `DELETE /portfolio/cas/batches/{id}`, `POST /portfolio/assets`, `GET /portfolio/assets`, `PUT /portfolio/assets/{id}`, `DELETE /portfolio/assets/{id}`, `GET /portfolio/net-worth`; all JWT-protected, ownership enforced
- **pdfplumber** added to backend dependencies

#### Frontend
- **Portfolio API client** (`src/lib/api/portfolio.ts`) — TypeScript interfaces and typed functions using the `api` fetch wrapper for all portfolio endpoints
- **PortfolioPage** (`/portfolio`) — three-tab layout (Net Worth, Mutual Funds, Other Assets)
  - *Net Worth tab*: total value card, stacked segment bar (equity/MF/manual), per-segment cards, manual asset type breakdown
  - *Mutual Funds tab*: drag-drop CAS upload zone (20 MB limit), batch history table with expandable holdings, delete batch
  - *Other Assets tab*: asset table with add/edit/delete, `AssetFormModal` with conditional fields per asset type
- **SimpleSelect** shared component (`src/components/ui/simple-select.tsx`) — thin wrapper around base-ui Select primitives accepting a flat `options` array; fixes Journal pages that used incorrect `options` prop on raw `SelectPrimitive.Root`
- **AppShell** — Portfolio nav item with Wallet icon added
- **Router** — `/portfolio` route registered

#### Bug fixes (Phase 10 Journal)
- `JournalPage` / `JournalEntryModal`: replaced `const { toast } = useToast()` with `const { success, error } = useToast()` (API mismatch)
- `JournalEntryModal`: fixed `<Dialog>` without `<DialogContent>` (no overlay rendered); now uses `<Dialog><DialogContent>` correctly
- `JournalPage`: fixed `Pagination` missing `pages` prop; fixed page state from 0-indexed to 1-indexed
- Removed invalid `variant="neutral"/"bull"/"bear"` Badge usage; replaced with themed inline spans

#### Tests (32 new passing — 327 total backend, 126 total frontend)
- `TestCasParser` (8) — header extraction, holding count, value parsing, multi-folio same AMC, missing closing balance, as-of-date from NAV line
- `TestCasUpload` (7) — upload creates batch, non-PDF rejected, auth required, list batches, get batch detail with holdings, 404 on missing, delete cascade
- `TestManualAssets` (10) — create gold/FD, invalid type 422, negative value 422, all 6 valid types, list, filter by type, update, delete, ownership isolation
- `TestNetWorth` (7) — empty state, manual assets aggregate, breakdown sorted by value, MF batch included, auth required

---

### Phase 8 — Paper Trading

#### Backend
- **Alembic migration** `g8h9i0j1k2l3` — creates `orders` and `positions` tables with partial indexes for open positions and time-based lookups; UUID PKs generated at Python level (no `server_default`)
- **ORM models** (`app/models/trading.py`) — `Order` (BUY/SELL, fill details, broker_payload JSONB) and `Position` (LONG/SHORT, avg_entry_price, trail_state, unrealized_pnl, realized_pnl, opened_at/closed_at)
- **Paper broker** (`app/broker/paper_broker.py`) — `place_paper_order` fills at Redis LTP → latest daily close fallback → signal entry_price; averages into existing open position for same stock/user/side; `close_position` creates closing order and computes realized P&L; `update_position_pnl` refreshes unrealized P&L
- **Circuit breaker** (`app/trading/circuit_breaker.py`) — blocks new orders when daily realized loss exceeds `capital_inr × daily_loss_limit_pct / 100` or `max_trades_per_day` is reached; uses IST calendar day window; never disableable
- **Trail SL state machine** (`app/trading/trail_sl.py`) — monotonic 4-state machine (none → breakeven → trailing_1 → trailing_2) based on R multiples; `advance_trail`, `is_sl_hit`, `is_tp_hit`, `compute_pnl`
- **Position monitor Celery task** (`app/tasks/position_monitor.py`) — runs every minute during market hours (9:15–15:30 IST = UTC 3:45–10:00, Mon–Fri); auto-closes on SL/TP hit; advances trail SL; refreshes unrealized P&L
- **Trading API** (`app/api/v1/trading.py`) — `POST /trading/orders` (circuit breaker enforced), `GET /trading/positions`, `POST /trading/positions/{id}/close`, `POST /trading/positions/{id}/update-sl`, `GET /trading/history` (paginated), `GET /trading/daily-pnl`

#### Frontend
- **Trading API client** (`src/lib/api/trading.ts`) — TypeScript interfaces and `tradingApi` with `placeOrder`, `getOpenPositions`, `closePosition`, `updateSl`, `getHistory`, `getDailyPnl`
- **DailyPnlCard** — shows realized P&L, loss limit progress bar, circuit breaker status; refetches every 60 s
- **PositionsPage** (`/trading/positions`) — open positions table with unrealized P&L, edit-SL and close buttons; `ClosePositionDialog` and `UpdateSlDialog` rendered via `createPortal` per floating-panel rules
- **TradeHistoryPage** (`/trading/history`) — paginated closed positions table with summary cards (page P&L, win rate, trade count)
- **Dashboard** — "Paper Buy" button added to each signal row; green-tinted with cart icon; shows loading state during mutation
- **AppShell** — Positions and Trade History nav links added

#### Tests (34 new passing, 302 total backend, 114 total frontend)
- `TestTrailSl` — 9 pure unit tests covering all state transitions (LONG/SHORT, breakeven, trailing_1, trailing_2, no-regression, zero-risk guard)
- `TestCircuitBreaker` — 3 async DB tests (loss-limit trigger, within-limit pass, max-trades trigger)
- `TestPaperBroker` — 5 integration tests (open+close full lifecycle, average-in, SL hit auto-close, TP hit auto-close, double-close raises)
- `TestTradingApi` — 17 API tests (auth, 404, circuit-breaker block, positions list, manual close, already-closed 409, SL update, invalid SL direction 422, history pagination, daily-pnl, cross-user isolation)
- Frontend: 12 tests across DailyPnlCard, PositionsPage, TradeHistoryPage

---

### Phase 7 — Live Data via Kite WebSocket

#### Backend
- **Kite OAuth flow** — `/broker/kite/login` returns Zerodha login URL; `/broker/kite/callback` exchanges `request_token` for `access_token`, persists `BrokerToken` (expires next 6 AM IST)
- **KiteInstrument sync** — `/broker/kite/instruments/sync` downloads Kite CSV and upserts into `kite_instruments` table; maps `exchange:symbol` → `instrument_token` for tick subscription
- **Candle aggregator** (`app/broker/candle_aggregator.py`) — stateful tick → OHLCV for 1m/5m/15m/1h; emits `CandleEvent` on new candle or close; look-ahead safe (compute N → signal valid from N+1)
- **Tick consumer** (`app/broker/tick_consumer.py`) — `KiteTicker` (thread) bridges to asyncio via `Queue`; publishes `ltp:{token}` and `candle:{table}:{stock_id}` to Redis pub/sub; upserts candles to DB; fires Celery task on candle close for signal regeneration
- **Gap fill** (`app/broker/gap_fill.py`) — on reconnect fetches Kite REST historical data for each missed timeframe and upserts
- **Live signal generation** — new Celery task `live_signal_generation` runs confluence engine on intraday candles (5m/15m/1h) for a single stock after each candle close
- **FastAPI WebSocket** (`/api/v1/ws/live`) — browser subscribes by symbol; server subscribes to Redis channels and fans out LTP + candle + signal events
- **Auto-resume** — FastAPI lifespan queries DB for active admin token and restarts tick consumer on server restart
- **Alembic migration** `f1g2h3i4j5k6` — creates `ohlcv_1m`, `ohlcv_5m`, `ohlcv_15m`, `ohlcv_1h` (TimescaleDB hypertables), `broker_tokens`, `kite_instruments`
- **Kite credentials** loaded from `.env` (`KITE_API_KEY`, `KITE_API_SECRET`, `KITE_REDIRECT_URL`)

#### Frontend
- **KiteConnectPage** (`/broker/kite`) — OAuth connect button, token status, sync instruments, start/stop consumer, setup checklist; admin-only route
- **`useLiveQuotes` hook** — WebSocket connection to `/api/v1/ws/live`; subscribes by symbol list; exposes `quotes` (LTP) and `candles` (latest per timeframe) maps; auto-reconnects every 3 s
- **Dashboard** — live LTP column in signals table; WebSocket connection indicator (green dot when connected)
- **AppShell** — "Kite" nav link for admin users

#### Tests (26 new passing)
- Candle aggregator: `_floor_to_period`, OHLC update, candle close event, 5m aggregation, zero-price guard, registry operations
- Gap fill: timeframe → Kite interval mapping, model mapping, gap calculation logic
- Broker API: login URL, auth guard, status endpoint, OAuth exchange (mocked Kite), bad token error, admin-only instrument sync

---

### Phase 5 — Signal Engine (Offline)

#### Backend — Analysis Engine
- **15 candlestick pattern detectors** — 6 single-candle (Marubozu ±0.8, Doji, Spinning Top, Hammer/Paper Umbrella +0.4/+0.7, Hanging Man −0.6, Shooting Star −0.7) and 4 multi-candle (Engulfing ±0.9, Harami ±0.5, Piercing/Dark Cloud ±0.7, Morning/Evening Star ±0.95) — scores match SIGNAL_ENGINE.md §2.1–2.2
- **10 indicator factors** — RSI level + divergence (wt 10), MACD cross + histogram (wt 10), EMA cross + price structure + multibagger bonus (wt 15/15/10), ADX regime (wt 5), BBands reversal (wt 10), Volume spike (wt 10)
- **Structural factors** — Dow Theory trend (wt 20), S/R zone + demand/supply detection (wt 10), Fibonacci retracement 0.5/0.618/0.786 levels (wt 5), FII/DII institutional flow (wt 5)
- **Confluence scorer** (`app/analysis/confluence.py`) — weighted average of all 14 factors, ADX regime adjustments (±5% threshold), min 70% confidence gate; returns `ConfluenceResult | None`
- **Risk sizer** (`app/analysis/risk.py`) — `compute_quantity = floor(capital × risk% / |entry − SL|)`; `compute_levels` per-classification SL/TP rules with max-SL guards (scalp 0.5%, intraday 0.5%, swing 8%)
- **Signal classifier** — maps timeframe → scalp/intraday/swing/positional
- **Expiry sweeper** — classification-correct validity (scalp +30 min, intraday 3:15 PM IST, swing +7 days, positional +42 days)
- **Signal generation service** — loads candles from DB, runs full pipeline, persists `Signal` ORM rows
- **Signal API** (`GET /signals/active`, `GET /signals/{id}`) — filterable by direction/classification/min_confidence, sorted by confidence desc; JWT-protected
- **Backtest harness** (`app/backtest/engine.py`) — anti-look-ahead (compute on N, fill at N+1 open); reports win_rate, avg_RR, max_drawdown, Sharpe, Sortino
- **Alembic migration** `d1e2f3a4b5c6` — creates `sr_levels`, `signals`, `signal_outcomes`, `strategy_runs`; fully reversible

#### Tests
- **219 total tests passing** — 189 new Phase 5 tests covering all pattern detectors, all indicators, Dow Theory, S/R/Fibonacci/institutional flow, confluence worked example from spec §3, risk sizer per-classification, signal API endpoints (auth, filters, pagination, 404)
- Anti-look-ahead bias verified in both fibonacci (uses `candles.iloc[:-1]` for prior swing) and backtest harness

---

### Phase 1 — Auth & User Master

#### Backend
- **JWT authentication** — access token (45 min, JS memory) + refresh token (7 d, httpOnly cookie)
- **Refresh token rotation** — each `/auth/refresh` call revokes the old session and issues a new one; JTI hash stored in `user_sessions` (raw token never persisted)
- **User CRUD API** (`/api/v1/users`) — admin-only list/create; self-service profile update; admin role-change gate; soft deactivation (no hard deletes)
- **Role-based deps** — `get_current_user` (Bearer + DB lookup) and `require_admin` FastAPI Depends
- **Alembic migration** `b4945c2d75aa` — creates `users` and `user_sessions` tables with `RESTART IDENTITY CASCADE` support
- **`scripts/create_admin.py`** — idempotent first-admin seed script
- **30 backend tests** — all passing; real Postgres test DB (`trading_platform_test`), `NullPool` isolation, no mocks

#### Frontend
- **Vite 8 + React 19 + TypeScript 6** scaffold with `@tailwindcss/vite` plugin
- **Design tokens** (`src/styles/tokens.css`) — trading-specific color palette: bull/bear/neutral, chart surface, brand dark theme
- **Global styles** (`src/styles/globals.css`) — base reset plus `card`, `btn`, `input`, `label`, `error-text` CSS primitives
- **API client** (`src/lib/api/client.ts`) — typed `fetch` wrapper with `ApiError` class
- **Auth & Users API modules** (`auth.ts`, `users.ts`)
- **Zustand auth store** — in-memory `accessToken` + `user`; survives re-renders, clears on logout
- **`useAuth` hook** — login, logout, refreshToken callbacks with 401 auto-clear
- **`AppShell`** — sticky header with brand logo, admin nav link, signed-in user email
- **`PageHeader`** — reusable title / subtitle / action-slot component
- **`LoginPage`** — email/password form with loading state and per-status error messages
- **`UsersPage`** (admin) — table with live TanStack Query fetch + "New user" modal
- **Protected routes** — `RequireAuth` and `RequireAdmin` guards in React Router v7
- **12 frontend tests** — Vitest + RTL; useAuth hook, LoginPage, UsersPage

#### Infrastructure
- Fixed postgres port mapping to 5433 (5432 was occupied by local Postgres)
- Added `make backend`, `make frontend`, `make migrate`, `make create-admin`, `make test`, `make lint`, `make typecheck`, `make check` targets
