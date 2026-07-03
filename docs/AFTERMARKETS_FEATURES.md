# Aftermarkets-Inspired Features

Four features from [aftermarkets.in](https://aftermarkets.in/) integrated into this platform. Each enhances the existing phases rather than adding new ones, except the advanced screener which gets its own sub-phase.

---

## 1. FII / DII institutional flow tracking

### What it is
Foreign Institutional Investors (FIIs) and Domestic Institutional Investors (DIIs) move markets. When FIIs aggressively buy a sector, that sector tends to rally; when they aggressively sell, retail money usually follows the drop. NSE publishes net buy/sell numbers daily after market close.

### Why it matters for our signal engine
Our confluence scorer becomes smarter when it knows whether smart money agrees with the technical setup. A bullish engulfing pattern on TATAMOTORS becomes higher-confidence if FIIs net bought ₹500 Cr of Auto sector stocks in the last 5 days.

### Implementation (Phase 4 add-on)

**Ingestion job** (`backend/app/ingestion/fii_dii_loader.py`):
- Runs daily at 6:30 PM IST via Celery beat
- Fetches from: `https://www.nseindia.com/api/fiidiiTradeReact`
- Stores in `fii_dii_daily` table (see schema)
- Also fetches per-stock bulk/block deals from BSE and NSE filing endpoints, stores in `bulk_block_deals`

**Signal engine integration** (`backend/app/analysis/structure/institutional.py`):
- New factor `institutional_flow` with weight 5
- Aggregates last 5 days of FII/DII for the stock's sector
- Returns score per Section 2.7 of `SIGNAL_ENGINE.md`

**Dashboard widget**:
- Daily FII/DII summary card on the dashboard ("FII net -₹1,247 Cr, DII net +₹892 Cr")
- 30-day FII/DII trend line chart
- "Stocks with heavy FII buying this week" panel (clickable to filter signal list)

---

## 2. Real-time corporate filings feed

### What it is
NSE and BSE publish corporate announcements continuously throughout the trading day — board meetings, financial results, dividends, mergers, rating changes, court orders, etc. Trading without watching these is like driving with one eye closed.

### Why it matters
A signal saying "BUY RELIANCE" 30 seconds before Reliance announces a board meeting to consider Jio listing is completely different from "BUY RELIANCE" on a quiet Tuesday. Corporate events change the risk profile.

### Implementation (Phase 6 add-on)

**Ingestion** (`backend/app/ingestion/filings_consumer.py`):
- Polls the NSE corporate announcements endpoint every 60 seconds during market hours
- Polls BSE every 60 seconds (offset by 30s to spread load)
- New filings classified by keyword regex into `filing_type` enum
- Stored in `corporate_filings` table

**Signal engine guard** (`backend/app/signals/event_guard.py`):
- If a stock has a high-impact filing in the last 30 minutes (earnings, merger, rating change), **suppress new signals** on that stock for 1 hour
- The rationale: technical analysis is invalidated during fundamental news events
- The user can override per-stock in settings

**Dashboard widget**:
- "Live filings" panel — chronological feed, filterable by watchlist
- Each filing card: stock symbol, headline, time, type icon, link to source
- Click filing → opens stock page with filing pinned at the top
- Optional desktop notification for filings on watchlisted stocks

**Sentiment scoring** (deferred to Phase 9):
- Use a lightweight transformer (FinBERT) to score filing headline sentiment from -1 to +1
- Feed into the institutional flow factor as a multiplier

---

## 3. Advanced screener (50+ filters)

### What it is
Currently planned as a basic category-tag filter on the stock master. Aftermarkets-style screeners expose every column we have as a filter, combinable with AND/OR logic.

### Why it matters
"Show me stocks that: are in Nifty50, have price > 50 EMA on daily, RSI between 40 and 60, FII net buying in last 5 days, market cap > ₹50,000 Cr, broke recent resistance in last 3 days" — this is the actual workflow of a serious trader.

### Implementation (Phase 2 enhancement)

**Backend** (`backend/app/api/v1/screener.py`):
- POST `/api/v1/screener/run` accepting a JSON filter spec:
  ```json
  {
    "filters": [
      {"field": "is_nifty50", "op": "eq", "value": true},
      {"field": "indicator.rsi_14", "op": "between", "value": [40, 60]},
      {"field": "indicator.price_vs_ema50", "op": "gt", "value": 0},
      {"field": "fundamental.market_cap_cr", "op": "gte", "value": 50000},
      {"field": "flow.fii_net_5d_cr", "op": "gt", "value": 0}
    ],
    "logic": "AND",
    "sort_by": "indicator.confidence_pct",
    "sort_dir": "desc",
    "limit": 50
  }
  ```
- Each `field` resolves to either a stocks-table column, a computed indicator value, or a join into another table
- Compiles to a single optimized SQL query (no N+1)

**Filter catalog** (`backend/app/screener/catalog.py`):
- Stocks-table filters: symbol, sector, industry, market_cap_cr, is_nifty50, is_banknifty, is_fno, listed_on
- Indicator filters: rsi, macd, ema, adx, bollinger position, price-vs-EMA, volume-vs-avg
- Pattern filters: any of our 15 patterns detected in last N candles
- Structure filters: at support/resistance/zone, fib bounce, swing high/low
- Flow filters: FII/DII net buying, bulk deals presence
- Filing filters: has filing in last N days, filing type
- Performance filters: 1d/5d/30d/YTD return, ATR-based volatility

**Frontend** (`frontend/src/features/screener/`):
- Filter builder UI — add/remove rows of `{field, operator, value}` triples
- Save/load named screens (per user)
- Pre-built starter screens: "Nifty50 RRBO candidates", "Pharma momentum", "F&O with FII inflow", etc.
- Results table with sortable columns, click stock → goes to detail page
- "Run as alert" button — turn the screen into an alert that fires when new stocks match

---

## 4. Conviction score validation

### What aftermarkets calls "conviction score backed by multi-signal convergence"

This is our confluence score by a different name. **No new feature needed** — but two enhancements:

### Enhancement 4a: Display individual factor breakdown
When a user clicks a signal on the dashboard, show a vertical bar chart of factors with their individual scores. This builds trust ("I can see why the system says 73% — pattern is +0.9, trend is +0.7, but volume only +0.3 because today's volume is unimpressive").

### Enhancement 4b: Conviction history per stock
For each stock, track the rolling 30-day average confluence score. A stock with a sustained 65–75% score range over 30 days is a "high-conviction" stock for the system. Expose this as a sortable column in the stock master.

---

## Priority for implementation

| Feature | Phase | Effort | Priority |
|---|---|---|---|
| Advanced screener | 2 enhancement | +3 days | high |
| FII/DII tracking | 4 add-on | +2 days | high |
| Corporate filings feed | 6 add-on | +3 days | medium |
| Conviction breakdown UI | 6 enhancement | +1 day | medium |
| Sentiment scoring (FinBERT) | 9 add-on | +3 days | low — defer |

---

## What we explicitly do NOT copy from aftermarkets

- Their UI design — we build our own clean Tailwind/shadcn experience
- Any proprietary data feeds — we use freely available NSE/BSE endpoints
- Their pricing model or marketing — we're personal-use first

If we ever rent out signal feed modules, we will respect SEBI Research Analyst registration requirements (publishing signals to external users without RA registration is a regulatory violation).
