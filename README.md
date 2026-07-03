# Trading Platform

Intelligent stock-suggestion and (future) algorithmic-trading system for Indian markets (NSE/BSE).

**Status:** Phase 0 — local dev infrastructure. No app code yet.

---

## What this is

A personal-first, rentable-later platform that:

1. Ingests live NSE/BSE data via the Zerodha Kite Connect WebSocket API.
2. Computes candlestick patterns, technical indicators (RSI, MACD, EMA, ADX, Bollinger), support/resistance zones, Fibonacci levels, and Dow-theory trend on multiple timeframes.
3. Combines them with a weighted confluence scorer to produce signals like *"Buy TATAMOTORS — Bullish engulfing at 50 EMA support, RSI 32, volume 1.6x avg, 78% confidence, SL ₹482, TP ₹512, qty 24."*
4. Stores every signal with its outcome for backtesting and continuous strategy tuning.
5. Starts in paper-trading mode; switches to live trading via broker API once strategies prove profitable.

The full 12-phase build plan lives in [`docs/PHASES.md`](docs/PHASES.md).

---

## Prerequisites

| Tool | Version | Verify |
|---|---|---|
| Docker | 20.10+ | `docker --version` |
| Docker Compose v2 | 2.0+ | `docker compose version` |
| Make | any recent | `make --version` |
| Git | 2.30+ | `git --version` |

If `docker compose version` says "command not found", you're on Compose v1. Either upgrade Docker Desktop, or replace `docker compose` with `docker-compose` everywhere — the Makefile auto-detects this.

---

## Quick start (Phase 0)

```bash
# 1. Clone & enter
git clone <your-repo-url> trading-platform
cd trading-platform

# 2. Copy env template and generate a real JWT secret
cp .env.example .env
# Open .env and replace JWT_SECRET_KEY with output of:
#   openssl rand -hex 32

# 3. Start the infrastructure
make up

# 4. Verify Postgres + TimescaleDB are alive
make db-extensions
```

You should see output similar to:

```
                                List of installed extensions
    Name     | Version |   Schema   |                            Description
-------------+---------+------------+--------------------------------------------------------------------
 pg_trgm     | 1.6     | public     | text similarity measurement
 pgcrypto    | 1.3     | public     | cryptographic functions
 plpgsql     | 1.0     | pg_catalog | PL/pgSQL procedural language
 timescaledb | 2.x.x   | public     | Enables scalable inserts and complex queries for time-series data
 uuid-ossp   | 1.1     | public     | generate universally unique identifiers (UUIDs)
```

If TimescaleDB is in that list, **Phase 0 is complete**. You're ready for Phase 1 (backend skeleton).

---

## Common commands

```bash
make help          # show all available commands
make up            # start postgres + redis
make up-tools      # also start pgAdmin web UI at http://localhost:5050
make down          # stop everything (data preserved)
make status        # health check
make db-shell      # open psql inside postgres container
make redis-shell   # open redis-cli inside redis container
make logs          # tail all logs
make clean         # DELETE ALL DATA (with confirmation)
```

---

## Project layout (target)

```
trading-platform/
├── backend/                  # FastAPI + Celery + SQLAlchemy + TA libs        (Phase 1+)
│   ├── app/
│   │   ├── api/v1/           # REST endpoints
│   │   ├── core/             # config, security, dependencies
│   │   ├── db/               # models + Alembic migrations
│   │   ├── ingestion/        # broker_ws, bhavcopy_loader, candle_aggregator
│   │   ├── analysis/         # patterns, indicators, S&R, fibonacci, dow
│   │   ├── signals/          # generator, expiry sweeper, confluence scorer
│   │   ├── trading/          # paper_broker, kite_broker
│   │   ├── backtest/         # engine, metrics, reports
│   │   ├── ws/               # WebSocket connection manager
│   │   └── tasks/            # Celery scheduled jobs
│   ├── tests/
│   ├── alembic/
│   └── pyproject.toml
│
├── frontend/                 # React + TypeScript + Vite + Tailwind            (Phase 1+)
│   └── src/
│       ├── pages/
│       ├── features/
│       ├── components/
│       └── hooks/
│
├── docker/                   # Service-specific docker config
│   └── postgres/init/        # SQL run once on first container start
│
├── docs/                     # Architecture docs, runbooks
│   └── PHASES.md             # the 12-phase build plan
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Why these tech choices

Brief reasoning; full discussion in [`docs/TECH_STACK.md`](docs/TECH_STACK.md) (added in Phase 1).

- **PostgreSQL + TimescaleDB** — relational data (users, signals, journals) and time-series data (5 years of 1-minute OHLCV) in one database with SQL joins between them. TimescaleDB hypertables make a 50-million-row candle table feel like 50 thousand rows.
- **Redis** — sub-millisecond reads for latest tick prices, Pub/Sub for WebSocket fan-out to many browser clients, Celery broker for scheduled jobs.
- **Python + FastAPI** — the entire quant ecosystem (pandas, numpy, TA-Lib, vectorbt) is Python-first. FastAPI's native async is essential for handling broker WebSockets + frontend WebSockets on one process.
- **React + Vite + TypeScript** — TypeScript catches half the frontend bugs at compile time. Vite has 10x faster hot-reload than CRA.
- **Tailwind + shadcn/ui** — you own the component code (unlike MUI), accessible by default, no vendor lock-in.
- **TradingView Lightweight Charts** — the same charting engine TradingView uses, free and open source. Best-in-class candlestick rendering.

---

## License

Personal use. Not for redistribution without owner consent.
