# CLAUDE.md — instructions for Claude Code

You are Claude Code working on a personal intelligent stock-suggestion and algo-trading platform for Indian markets (NSE/BSE). This file is your authoritative project context. Read it fully at the start of every session.

## Project owner profile

- Solo developer, building for personal use first, with possible future productization (renting out modules like signal feed, journal, backtester).
- Has attended a trading masterclass; the platform encodes those specific strategies (RRBO swing, DC1/DC2 intraday, option selling passive income, multibagger EMA, etc.). The strategy logic in `docs/SIGNAL_ENGINE.md` is non-negotiable — it is the user's edge.
- Has an existing rough prototype on local machine. Before writing new code in any module, **search the user's prototype directory for prior art** (the user will tell you the path). Salvage what's correct; ignore what isn't. Never copy patterns from random GitHub repos.

## Hard constraints (do not negotiate these)

1. **All code is written from scratch in this repo.** Do not paste from external sources without thorough review and rewriting. Bug-free, audited code is the goal.
2. **Every feature ships with tests.** No exceptions. Test → implement → refactor. If you find yourself wanting to skip tests "just this once", you are about to ship a bug.
3. **No public signup.** Users are created only by admins through the user master.
4. **Trade signals must come from the confluence engine, not single indicators.** A solo RSI<30 is never a buy signal in this system. See `docs/SIGNAL_ENGINE.md` Section 3.
5. **Position sizing is mandatory.** Every signal must include suggested quantity computed from `risk_amount / (entry - stop_loss)`. No "round numbers."
6. **Signal validity is classification-dependent**, not a flat 30 minutes. See `docs/SIGNAL_ENGINE.md` Section 5.
7. **Paper trading must be the default mode.** Live trading is gated behind explicit user opt-in plus a 30-day paper-trading profitability check.
8. **Never disable the daily-loss circuit breaker** in live mode, regardless of user request.
9. **All currency in INR.** All timestamps stored in UTC, displayed in IST.
10. **Financial UI rules are mandatory.** See `docs/UI_GUIDELINES.md`. Any new component touching prices, P&L, signals, or trades must follow it. Numbers are tabular-nums, right-aligned in tables, formatted via `lib/format.ts`, and coloured via `--color-profit` / `--color-loss` tokens — never with raw `text-green-500` / `text-red-500`.

## Tech stack (locked in)

| Layer | Choice |
|---|---|
| Backend language | Python 3.12 |
| Backend framework | FastAPI (async) |
| Task queue | Celery + Redis |
| Database | PostgreSQL 16 + TimescaleDB extension |
| Cache / Pub-Sub | Redis 7 |
| Frontend | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS + shadcn/ui |
| Charts | TradingView Lightweight Charts (candles) + Recharts (dashboards) |
| State | Zustand + TanStack Query |
| Auth | JWT (access in memory, refresh in httpOnly cookie) |
| Broker API | Zerodha Kite Connect (₹500/mo paid plan for data) |
| Testing | pytest (backend), Vitest + RTL (frontend), Playwright (E2E) |
| Reverse proxy | Caddy |
| Deployment | Docker Compose; local dev first, VPS later |

Do not substitute these without asking the user. Each was chosen for specific reasons; see `docs/TECH_STACK_RATIONALE.md` if you need to know why.

## Architecture in one paragraph

Five tiers, data flows top-down. **(1) External sources:** Kite WebSocket for live ticks, NSE bhavcopy CSVs for EOD, NSE FII/DII reports, BSE/NSE corporate filings RSS, CAMS CAS for mutual funds. **(2) Ingestion:** async Python workers consume each source, normalize, and write to Postgres+Timescale (history) and Redis (latest LTP). **(3) Processing core:** candle aggregator builds 5m/15m/1h/1d from ticks; pattern detector, indicator engine, S&R/zone detector, and Fibonacci compute on every new candle; confluence scorer combines them into a weighted signal with confidence %; risk sizer attaches SL/TP/quantity. **(4) Storage:** Postgres for everything relational and time-series, Redis for hot data and pub/sub. **(5) Presentation:** FastAPI REST for CRUD and WebSocket for live signal push; React dashboard consumes both. Paper-trading and (later) live Kite trading sit alongside as siblings of the REST layer.

## Phase workflow (12 phases — see docs/PHASES.md for details)

Always work one phase at a time. Within a phase, build a vertical slice: model → migration → service → API → frontend page → tests, in that order. **Do not start phase N+1 until phase N has green tests and a working demo.**

| # | Phase | Key deliverable |
|---|---|---|
| 0 | Infrastructure | `make up` brings up Postgres + Redis ← already done |
| 1 | Auth & user master | Login, JWT, admin-only user creation |
| 2 | Stock master + screener | Nifty50 / BankNifty / F&O stocks; aftermarkets-style 50+ filter screener |
| 3 | Categories master | Many-to-many tagging, filter by category |
| 4 | EOD ingestion | 5 yrs daily OHLCV + FII/DII daily flows |
| 5 | **Signal engine (offline)** | Confluence scorer + backtest harness — most important phase |
| 6 | Dashboard v1 | Signal list, candlestick chart, corporate filings feed |
| 7 | Live data via Kite | WebSocket tick consumer, 5m/15m candle aggregation, real-time signal push |
| 8 | Paper trading | Virtual orders, position tracking, P&L. **Run ≥ 30 days before Phase 12.** |
| 9 | Strategy lab | Backtest UI; rank factor combinations by win rate / Sharpe / drawdown |
| 10 | Trading journal | Auto-populated from trades, manual notes, emotion tags |
| 11 | External portfolio | CAMS CAS import for MFs, manual entries for gold/SIPs |
| 12 | Live trading | Kite order placement with daily-loss circuit breaker. Static IP required. |

## How to handle the user's existing rough code


The user has prior work. Treat it as **reference, not gospel**.

1. Ask the user for the absolute path to their prototype directory (e.g., `~/dev/trading-rough/`).
2. Run a structural inspection first: `tree -L 3` and `find . -name "*.py" -o -name "*.tsx"` to map the territory.
3. For each module you're about to build, search the prototype for relevant files. Read them critically:
   - **Salvage** specific algorithms, formulas, or domain logic that's correct.
   - **Discard** boilerplate, half-finished features, or anything not matching our tech stack.
   - **Question** any pattern that contradicts this CLAUDE.md or the spec docs.
4. Never blindly port code. When you find something useful, explain to the user *why* it's worth keeping, then rewrite it cleanly in the new codebase with tests.

## Detailed specifications

Read these before working on the relevant phase:

- `docs/PHASES.md` — full phase plan with deliverables, decision gates, calendar estimates
- `docs/SIGNAL_ENGINE.md` — the heart of the system: every pattern, indicator, weight, classification rule, validity rule, position-sizing formula
- `docs/DATABASE_SCHEMA.sql` — full Postgres+Timescale schema with comments
- `docs/AFTERMARKETS_FEATURES.md` — FII/DII tracking, corporate filings, advanced screener spec
- `docs/CLAUDE_CODE_GUIDE.md` — workflow tips, common commands, anti-patterns to avoid
- `docs/TECH_STACK_RATIONALE.md` — why we chose each tool

## Communication style

- Be direct and concrete. The user dislikes filler.
- When making non-trivial design decisions, surface trade-offs explicitly and ask before committing.
- When you discover bugs in already-built code, fix them but mention what you found.
- When the user asks "is X possible / good", give them an honest yes/no with one-line reasoning, not three paragraphs.
- Use `sendPrompt`-style options sparingly — once per multi-step decision, not every message.

## Common pitfalls to avoid

- **Don't trust pandas defaults on time data.** Always specify `tz='Asia/Kolkata'` for IST market data; convert to UTC for storage.
- **Don't compute indicators on incomplete candles.** A 5-minute candle at 9:17 AM (2 minutes in) is not done forming. Tag candles `is_complete=true` only after the period closes.
- **Don't generate signals on the same candle that triggers them.** Look-ahead bias destroys backtests. Compute on candle N, generate signal valid from candle N+1 open.
- **Don't store floats for prices.** Use `Numeric(12, 4)` in Postgres, `Decimal` in Python. Floats accumulate rounding errors that compound into wrong P&L.
- **Don't fan out WebSocket events synchronously.** Use Redis pub/sub so a slow client can't block fast ones.
- **Don't hard-code the JWT secret.** Always read from `os.environ`. Fail loudly if missing.

## Frontend component rules

### Floating panels (dropdowns, popovers, tooltips, dialogs)
- Layout regions: `<aside>` (sidebar) gets `relative z-20`; `<header>` (topbar) gets `relative z-30`; `<main>` gets no explicit z-index.
- Any floating panel that opens from inside `<main>` (which has `overflow-y: auto`) **must** render via `createPortal(panel, document.body)` and position itself using `getBoundingClientRect()` on the trigger. Portals escape overflow clipping.
- **Never** use `/50`, `/30`, `/20` Tailwind opacity on background colors of solid surfaces. Semi-transparent panel backgrounds bleed through page content visually.

### Form controls
- **Never** use raw `<select>`, `<input type="checkbox">`, or `<input type="range">` in feature pages. Always use the themed component from `@/components/ui/` (`Select`, `Checkbox`, `Slider`, etc.). Native elements do not match the dark theme and have poor UX (e.g., native select shows no loading state, OS-styled dropdown).

### shadcn/base-ui defaults
- Every time you add a new component from shadcn/base-ui, audit it for: (1) `dark:` utility classes that conflict with our `data-theme="light"` approach; (2) `bg-muted/50` or other semi-transparent backgrounds; (3) `text-foreground` / `text-muted-foreground` — verify these resolve to the right `--color-*` vars in our `tokens.css`.

## Definition of done (per feature)

A feature is done when **all** of the following are true:

- [ ] Tests pass: `pytest backend/tests/` and `npm test --prefix frontend`
- [ ] Linter passes: `ruff check backend/` and `npm run lint --prefix frontend`
- [ ] Type checker passes: `mypy backend/app/` and `npm run typecheck --prefix frontend`
- [ ] Manual smoke test: feature visibly works end-to-end in browser
- [ ] Migration is reversible: `alembic downgrade -1` succeeds
- [ ] No new TODOs or commented-out code merged
- [ ] CHANGELOG.md updated under "Unreleased"
