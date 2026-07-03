# Tech stack rationale

Every choice has a competing alternative. Here's why we picked what we picked, and the cost of going against any of these.

---

## Backend language: Python 3.12

**Why:** The entire quant ecosystem (pandas, numpy, TA-Lib, vectorbt, scikit-learn) is Python-native. Indicator math, backtesting, and ML are all 10x easier here.

**Cost of switching:** Node.js has `technicalindicators` but no equivalent to vectorbt; you'd reinvent backtesting. Go has speed but minimal TA libraries. Java is verbose and overkill for personal scale.

**Why 3.12 specifically:** Faster than 3.11 (per-language benchmarks), proper `TypedDict` and `Self` types, no broken async patterns.

---

## Backend framework: FastAPI

**Why:** Native async (essential for handling broker WebSocket + many frontend WebSockets concurrently), auto-generated OpenAPI docs (frontend gets typed client free), Pydantic validation (catches bad requests before they hit business logic).

**Cost of switching:** Django REST Framework is heavier and sync-first; you'd fight it for WebSocket. Flask is fine but you build everything (validation, schemas, docs) yourself. Litestar is modern alternative but smaller ecosystem.

---

## Task queue: Celery + Redis

**Why:** Battle-tested for scheduled jobs (EOD reconciliation, signal expiry sweeps, nightly backtests). Redis as broker is already in our stack.

**Cost of switching:** APScheduler is simpler but doesn't survive restarts. RQ is lighter but lacks Celery's retry/chain primitives. Dramatiq is good but smaller community.

---

## Database: PostgreSQL 16 + TimescaleDB

**Why one database:** Your data has two distinct shapes — relational (users, signals, journals) and time-series (5+ years of 1-minute OHLCV per stock = ~50M rows). TimescaleDB is a Postgres *extension* that turns regular tables into hypertables (time-partitioned, with chunk pruning). You get SQL joins between user.id and a hypertable in a single query.

**Cost of switching:**
- **InfluxDB** for time-series + Postgres for relational: two databases to manage, two connection pools, two backup strategies, no cross-database joins.
- **MongoDB** would be wrong here. Your data has heavy referential integrity (signals reference stocks reference categories) and money columns that need ACID. NoSQL trades these for a problem you don't have.
- **DuckDB** is great for backtests (in-process columnar OLAP) but bad for live (no concurrent writes). We *might* use it inside the backtest engine in Phase 9 alongside Postgres.

---

## Cache + pub-sub: Redis 7

**Why:** Sub-millisecond reads for latest LTP (price ticker on UI). Pub-sub channels for fanning out new signals to all connected browsers. Already used by Celery.

**Cost of switching:**
- **Memcached** has no pub-sub.
- **Valkey** (Redis fork) is fine but ecosystem is smaller.
- **In-memory Python dict** doesn't survive restarts and doesn't fan out across processes.

---

## Frontend: React 18 + TypeScript + Vite

**Why React:** Largest component ecosystem; shadcn/ui, Lightweight Charts, TanStack Query all React-first.

**Why TypeScript:** Catches half the frontend bugs at compile time. For a trading app where a wrong currency calculation = real money lost, type safety is essential.

**Why Vite over CRA:** CRA is deprecated. Vite has 10x faster hot reload, native ESM, and a saner build pipeline.

**Cost of switching:**
- **Vue** or **Svelte** are equally good frameworks but have smaller ecosystems for financial charts.
- **Next.js** is overkill — we don't need SSR for a logged-in app.

---

## Styling: Tailwind CSS + shadcn/ui

**Why Tailwind:** Utility classes mean no CSS file sprawl. Theme tokens are explicit. Easy dark mode.

**Why shadcn/ui:** Unlike MUI/Chakra, you *own* the component code (it's copy-pasted into your repo). No vendor lock-in. Accessible by default. Easy to customize.

**Cost of switching:** Plain CSS — slower iteration. MUI — vendor lock-in, hard to escape later.

---

## Charting: TradingView Lightweight Charts + Recharts

**Why two libraries:**
- **Lightweight Charts** (free, open-source from TradingView): same engine TradingView itself uses for candlesticks. Hardware-accelerated, hand-tuned for OHLCV. No real competitor for serious candlestick rendering.
- **Recharts** for simple dashboards (P&L curve, equity, win-rate over time). Smaller and more declarative than D3.

**Cost of switching:** ApexCharts is decent. Highcharts is paid for commercial. Plotly is heavy.

---

## State: Zustand + TanStack Query

**Why Zustand for UI state:** 10x simpler than Redux. No reducers, no boilerplate. 1KB.

**Why TanStack Query for server state:** Caching, deduplication, stale-while-revalidate, WebSocket invalidation all built-in. Eliminates 80% of useEffect patterns you'd otherwise write.

**Cost of switching:**
- **Redux Toolkit** works but is 5x more code per feature.
- **Recoil/Jotai** are fine alternatives to Zustand; pick one and move on.

---

## Auth: JWT (access in memory + refresh in httpOnly cookie)

**Why this exact pattern:**
- Access token in JS memory: short-lived (15 min), not vulnerable to XSS-stealing localStorage attacks.
- Refresh token in httpOnly cookie: not readable by JS, sent automatically with same-origin requests, mitigates CSRF with `SameSite=Strict`.
- Refresh on every page load, rotate on every refresh.

**Cost of doing it wrong:**
- Putting JWT in localStorage = an XSS bug exfiltrates all tokens.
- Long-lived JWT = stolen token usable for days.
- Session cookies alone = harder to use across subdomains if you ever scale.

---

## Broker: Zerodha Kite Connect

**Why:**
- You already have it set up
- ₹500/mo for live + historical + WebSocket — cheapest serious option
- 10 years of intraday history available (critical for backtesting)
- The kiteconnect Python SDK is the most mature broker SDK in India
- Largest user community = best Stack Overflow / forum coverage

**Alternatives considered:**
- **Angel One SmartAPI** — free, decent, but SDK quality and rate limits are inferior
- **Dhan API** — free, modern, smaller community
- **Upstox API** — free, decent
- **Fyers** — free, decent

We can swap brokers behind a `BrokerInterface` abstraction (Phase 7+); the rest of the system doesn't care.

---

## Deployment: Docker Compose → optional VPS

**Why Docker Compose for v1:** Reproducible local dev. Same `docker-compose.yml` works on a VPS later.

**Cost of skipping Docker:** "Works on my machine" syndrome the moment you try to deploy.

**When to graduate to Kubernetes:** Only if you actually rent out modules to paying users. For personal use, a single 4GB VPS handles all of this trivially.

---

## Testing: pytest + Vitest + Playwright

**Why pytest:** Fixtures, parametrize, async support, plugin ecosystem.

**Why Vitest over Jest:** Native ESM, faster, same API. Bundled with Vite.

**Why Playwright for E2E:** Records selectors automatically, parallel execution, screenshots on failure.

---

## Reverse proxy: Caddy

**Why:** Auto HTTPS via Let's Encrypt out of the box (when we deploy). One-config-file simplicity. Nginx works but takes 5x the config.

**For local dev:** Not needed. We use Vite dev server (5173) and uvicorn (8000) directly.

---

## What we explicitly did NOT pick, and why

| Tool | Why not |
|---|---|
| GraphQL | REST is enough; no over/under-fetching problem at our scale |
| MongoDB | Heavy relational data + ACID need = use Postgres |
| Microservices | Personal-scale monolith. Microservices when traffic demands it. |
| Kubernetes | Same. Compose until you need otherwise. |
| Kafka | Redis pub/sub handles our message volume easily |
| Webpack | Vite is strictly better |
| ESLint + Prettier separately | Use Biome (single tool) — TBD whether we adopt it in Phase 1 |
| Yarn / npm | Use `pnpm` — disk-efficient, faster, strict |
