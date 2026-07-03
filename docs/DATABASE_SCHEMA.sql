-- =============================================================================
-- Trading Platform — full database schema reference
-- =============================================================================
-- This file is the authoritative reference for the data model.
-- The actual migrations are Alembic-managed (backend/alembic/versions/).
-- Use this file to understand the *shape* of the data; use Alembic to evolve it.
--
-- Conventions:
--   - Primary keys: BIGSERIAL for entities with many rows; UUID for signals,
--     journal entries, audit log (we want non-sequential IDs).
--   - Timestamps: ALL stored as TIMESTAMPTZ (UTC). Display layer converts to IST.
--   - Money/prices: NUMERIC(precision, scale). NEVER floats.
--   - Soft delete: prefer is_active flag over hard delete for entities.
--   - JSONB for flexible config (factor_scores, broker_payload, etc.)
-- =============================================================================


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ AUTHENTICATION & USER MANAGEMENT                                        │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,           -- bcrypt
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(32)  NOT NULL DEFAULT 'user',
                                                     -- 'admin' | 'user' | 'readonly'
    capital_inr           NUMERIC(14, 2) DEFAULT 100000.00,  -- trading capital
    risk_per_trade_pct    NUMERIC(5, 2)  DEFAULT 2.00,       -- max % to risk per trade
    daily_loss_limit_pct  NUMERIC(5, 2)  DEFAULT 3.00,       -- circuit breaker threshold
    max_trades_per_day    INT            DEFAULT 2,          -- masterclass discipline rule
    is_active             BOOLEAN        NOT NULL DEFAULT true,
    trading_mode          VARCHAR(16)    NOT NULL DEFAULT 'paper',
                                                     -- 'paper' | 'semi_auto' | 'live'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;

CREATE TABLE user_sessions (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  VARCHAR(255) NOT NULL,       -- never store raw tokens
    ip_address          INET,
    user_agent          TEXT,
    expires_at          TIMESTAMPTZ NOT NULL,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_expiry ON user_sessions(expires_at) WHERE revoked_at IS NULL;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ STOCK UNIVERSE                                                          │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE stocks (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,            -- 'TATAMOTORS', 'RELIANCE'
    exchange        VARCHAR(8)  NOT NULL,            -- 'NSE' | 'BSE'
    isin            VARCHAR(16) UNIQUE,              -- canonical international ID
    company_name    VARCHAR(255) NOT NULL,
    sector          VARCHAR(64),                     -- 'Auto', 'IT', 'Pharma'
    industry        VARCHAR(64),                     -- finer than sector
    market_cap_cr   NUMERIC(14, 2),                  -- in crores INR
    lot_size        INT NOT NULL DEFAULT 1,          -- F&O lot size; 1 for equity
    tick_size       NUMERIC(8, 4) NOT NULL DEFAULT 0.05,
    is_fno          BOOLEAN NOT NULL DEFAULT false,  -- in the 186 F&O list
    is_nifty50      BOOLEAN NOT NULL DEFAULT false,
    is_banknifty    BOOLEAN NOT NULL DEFAULT false,
    is_finnifty     BOOLEAN NOT NULL DEFAULT false,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    listed_on       DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(symbol, exchange)
);

CREATE INDEX idx_stocks_symbol ON stocks(symbol);
CREATE INDEX idx_stocks_symbol_trgm ON stocks USING gin(symbol gin_trgm_ops);  -- fuzzy search
CREATE INDEX idx_stocks_name_trgm  ON stocks USING gin(company_name gin_trgm_ops);
CREATE INDEX idx_stocks_sector ON stocks(sector) WHERE is_active = true;
CREATE INDEX idx_stocks_fno    ON stocks(is_fno)    WHERE is_active = true;

-- aftermarkets.in style screener will query on many columns; partial indexes
-- on is_active=true keep them lean.


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CATEGORIES (user-defined tagging, many-to-many with stocks)             │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE categories (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(64) NOT NULL UNIQUE,        -- 'Pharma', 'EV', 'Defence', 'AI'
    slug        VARCHAR(64) NOT NULL UNIQUE,
    description TEXT,
    created_by  BIGINT REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stock_categories (
    stock_id    BIGINT NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    tagged_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    tagged_by   BIGINT REFERENCES users(id),
    PRIMARY KEY (stock_id, category_id)
);

CREATE INDEX idx_stock_cat_category ON stock_categories(category_id);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ INDICES (Nifty50, BankNifty, etc.) and their constituents               │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE indices (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(32) NOT NULL UNIQUE,        -- 'NIFTY50', 'BANKNIFTY'
    name        VARCHAR(128) NOT NULL,
    exchange    VARCHAR(8) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE index_constituents (
    index_id    BIGINT NOT NULL REFERENCES indices(id) ON DELETE CASCADE,
    stock_id    BIGINT NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    weight_pct  NUMERIC(6, 3),                      -- e.g., 11.250 for RELIANCE in NIFTY50
    added_on    DATE NOT NULL DEFAULT CURRENT_DATE,
    removed_on  DATE,                               -- null = currently in index
    PRIMARY KEY (index_id, stock_id, added_on)
);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TIME-SERIES: OHLCV CANDLES (TimescaleDB hypertables)                    │
-- └─────────────────────────────────────────────────────────────────────────┘
-- These tables are converted to hypertables for time-based partitioning.
-- A 5-year history of 1-minute Nifty50 candles is ~50 million rows; this would
-- be slow on a plain Postgres table but is sub-millisecond on a hypertable.

CREATE TABLE ohlcv_1m (
    time        TIMESTAMPTZ NOT NULL,
    stock_id    BIGINT NOT NULL,
    open        NUMERIC(12, 4) NOT NULL,
    high        NUMERIC(12, 4) NOT NULL,
    low         NUMERIC(12, 4) NOT NULL,
    close       NUMERIC(12, 4) NOT NULL,
    volume      BIGINT NOT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT false      -- false until period closes
);

SELECT create_hypertable('ohlcv_1m', 'time', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX idx_ohlcv1m_stock_time ON ohlcv_1m (stock_id, time DESC);

-- Same shape for higher timeframes — derived from 1m via continuous aggregates,
-- OR ingested directly from broker for some timeframes.
CREATE TABLE ohlcv_5m  (LIKE ohlcv_1m INCLUDING ALL);
CREATE TABLE ohlcv_15m (LIKE ohlcv_1m INCLUDING ALL);
CREATE TABLE ohlcv_1h  (LIKE ohlcv_1m INCLUDING ALL);
CREATE TABLE ohlcv_1d  (LIKE ohlcv_1m INCLUDING ALL);

SELECT create_hypertable('ohlcv_5m',  'time', chunk_time_interval => INTERVAL '1 month');
SELECT create_hypertable('ohlcv_15m', 'time', chunk_time_interval => INTERVAL '1 month');
SELECT create_hypertable('ohlcv_1h',  'time', chunk_time_interval => INTERVAL '3 months');
SELECT create_hypertable('ohlcv_1d',  'time', chunk_time_interval => INTERVAL '1 year');

CREATE INDEX idx_ohlcv5m_stock_time  ON ohlcv_5m  (stock_id, time DESC);
CREATE INDEX idx_ohlcv15m_stock_time ON ohlcv_15m (stock_id, time DESC);
CREATE INDEX idx_ohlcv1h_stock_time  ON ohlcv_1h  (stock_id, time DESC);
CREATE INDEX idx_ohlcv1d_stock_time  ON ohlcv_1d  (stock_id, time DESC);

-- Retention policy: keep 5 years of 1m data, 10 years of 1d data.
-- Older chunks are auto-dropped by TimescaleDB.
SELECT add_retention_policy('ohlcv_1m', INTERVAL '5 years');
SELECT add_retention_policy('ohlcv_5m', INTERVAL '5 years');


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ FII / DII INSTITUTIONAL FLOWS (aftermarkets.in-inspired)                │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE fii_dii_daily (
    trade_date      DATE NOT NULL,
    investor_type   VARCHAR(8) NOT NULL,            -- 'FII' | 'DII'
    segment         VARCHAR(16) NOT NULL,           -- 'cash' | 'futures' | 'options'
    buy_value_cr    NUMERIC(14, 2) NOT NULL,        -- crore INR
    sell_value_cr   NUMERIC(14, 2) NOT NULL,
    net_value_cr    NUMERIC(14, 2) GENERATED ALWAYS AS (buy_value_cr - sell_value_cr) STORED,
    PRIMARY KEY (trade_date, investor_type, segment)
);

CREATE INDEX idx_fii_dii_date ON fii_dii_daily(trade_date DESC);

-- Bulk and block deals (per-stock institutional moves)
CREATE TABLE bulk_block_deals (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    deal_type       VARCHAR(8) NOT NULL,            -- 'bulk' | 'block'
    client_name     VARCHAR(255),                   -- entity name from filing
    transaction     VARCHAR(8) NOT NULL,            -- 'BUY' | 'SELL'
    quantity        BIGINT NOT NULL,
    price           NUMERIC(12, 4) NOT NULL,
    value_cr        NUMERIC(14, 2) GENERATED ALWAYS AS (quantity * price / 10000000) STORED,
    source          VARCHAR(16) NOT NULL,           -- 'NSE' | 'BSE'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_deals_stock_date ON bulk_block_deals(stock_id, trade_date DESC);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CORPORATE FILINGS (aftermarkets.in-inspired live feed)                  │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE corporate_filings (
    id              BIGSERIAL PRIMARY KEY,
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    filing_type     VARCHAR(32) NOT NULL,
        -- 'board_meeting' | 'earnings' | 'dividend' | 'split' | 'bonus'
        -- | 'merger' | 'agm' | 'rating_change' | 'other'
    headline        TEXT NOT NULL,
    body            TEXT,
    filing_date     DATE NOT NULL,
    filing_time     TIMESTAMPTZ NOT NULL,
    source          VARCHAR(16) NOT NULL,           -- 'NSE' | 'BSE'
    source_url      TEXT,
    sentiment_score NUMERIC(4, 3),                  -- -1.000 to +1.000 (Phase 6+ ML)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_filings_stock_time ON corporate_filings(stock_id, filing_time DESC);
CREATE INDEX idx_filings_time       ON corporate_filings(filing_time DESC);
CREATE INDEX idx_filings_type       ON corporate_filings(filing_type, filing_time DESC);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ SUPPORT / RESISTANCE LEVELS (computed by analysis engine)               │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE sr_levels (
    id              BIGSERIAL PRIMARY KEY,
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    timeframe       VARCHAR(8) NOT NULL,            -- '15m' | '1h' | '1d'
    level_type      VARCHAR(16) NOT NULL,           -- 'support' | 'resistance' | 'demand_zone' | 'supply_zone'
    price_lower     NUMERIC(12, 4) NOT NULL,        -- equals price for line levels
    price_upper     NUMERIC(12, 4) NOT NULL,        -- equals price for line levels
    strength        INT NOT NULL DEFAULT 1,         -- number of times tested
    first_touched_at TIMESTAMPTZ NOT NULL,
    last_touched_at  TIMESTAMPTZ NOT NULL,
    is_broken       BOOLEAN NOT NULL DEFAULT false,
    broken_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sr_stock_tf ON sr_levels(stock_id, timeframe, is_broken);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ SIGNALS — the core output of the engine                                 │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE signals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stock_id            BIGINT NOT NULL REFERENCES stocks(id),
    direction           VARCHAR(8) NOT NULL,        -- 'BUY' | 'SELL' (short)
    classification      VARCHAR(16) NOT NULL,       -- 'scalp' | 'intraday' | 'swing' | 'positional'
    timeframe           VARCHAR(8) NOT NULL,        -- timeframe that triggered
    entry_price         NUMERIC(12, 4) NOT NULL,
    stop_loss           NUMERIC(12, 4) NOT NULL,
    take_profit         NUMERIC(12, 4) NOT NULL,
    suggested_qty       INT NOT NULL,
    risk_reward_ratio   NUMERIC(5, 2) GENERATED ALWAYS AS (
        ABS(take_profit - entry_price) / NULLIF(ABS(entry_price - stop_loss), 0)
    ) STORED,
    confidence_pct      INT NOT NULL,               -- 0-100
    factor_scores       JSONB NOT NULL,             -- {factor_name: {weight, score, explanation}}
    triggering_patterns TEXT[],                     -- ['BULLISH_ENGULFING', 'HAMMER']
    triggering_indicators TEXT[],                   -- ['RSI_DIVERGENCE', 'MACD_CROSS']
    headline            TEXT NOT NULL,              -- human-readable summary

    status              VARCHAR(16) NOT NULL DEFAULT 'active',
        -- 'active' | 'expired' | 'hit_tp' | 'hit_sl' | 'manually_closed'
    validity_until      TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expired_at          TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    outcome_pnl_pct     NUMERIC(7, 3)               -- populated by reconcile job
);

CREATE INDEX idx_signals_stock_status ON signals(stock_id, status);
CREATE INDEX idx_signals_active       ON signals(validity_until) WHERE status = 'active';
CREATE INDEX idx_signals_created      ON signals(created_at DESC);
CREATE INDEX idx_signals_class        ON signals(classification, created_at DESC);

-- Outcome tracking — populated by EOD reconciliation
CREATE TABLE signal_outcomes (
    signal_id           UUID PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
    hit_target          BOOLEAN NOT NULL,
    hit_sl              BOOLEAN NOT NULL,
    max_favorable_pct   NUMERIC(7, 3),              -- best % move in trade direction
    max_adverse_pct     NUMERIC(7, 3),              -- worst % move against direction
    exit_price          NUMERIC(12, 4),
    exit_time           TIMESTAMPTZ,
    pnl_pct             NUMERIC(7, 3) NOT NULL,
    notes               TEXT
);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ STRATEGY PERFORMANCE (Phase 9 strategy lab)                             │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE strategy_runs (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    factor_weights      JSONB NOT NULL,             -- {factor_name: weight}
    timeframe           VARCHAR(8) NOT NULL,
    universe            VARCHAR(64) NOT NULL,       -- 'NIFTY50' | 'BANKNIFTY' | 'FNO' | 'ALL'
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    total_trades        INT NOT NULL,
    winning_trades      INT NOT NULL,
    win_rate_pct        NUMERIC(5, 2) GENERATED ALWAYS AS (
        100.0 * winning_trades / NULLIF(total_trades, 0)
    ) STORED,
    avg_rr              NUMERIC(5, 2),
    sharpe              NUMERIC(6, 3),
    sortino             NUMERIC(6, 3),
    max_drawdown_pct    NUMERIC(6, 3),
    avg_holding_days    NUMERIC(6, 2),
    ranking             INT,                        -- rank among compared strategies
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_strategy_period ON strategy_runs(period_start, period_end);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ PAPER + LIVE TRADING                                                    │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    signal_id       UUID REFERENCES signals(id),    -- null for manual trades
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    mode            VARCHAR(8) NOT NULL,            -- 'paper' | 'live'
    side            VARCHAR(8) NOT NULL,            -- 'BUY' | 'SELL'
    order_type      VARCHAR(16) NOT NULL,           -- 'MARKET' | 'LIMIT' | 'SL' | 'SL-M'
    quantity        INT NOT NULL,
    price           NUMERIC(12, 4),                 -- limit price; null for MARKET
    trigger_price   NUMERIC(12, 4),                 -- for SL/SL-M
    status          VARCHAR(16) NOT NULL DEFAULT 'pending',
        -- 'pending' | 'open' | 'filled' | 'partial' | 'cancelled' | 'rejected'
    broker_order_id VARCHAR(64),                    -- Kite order ID when live
    placed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    filled_at       TIMESTAMPTZ,
    filled_price    NUMERIC(12, 4),
    filled_qty      INT,
    error_message   TEXT,
    broker_payload  JSONB                           -- raw broker response for audit
);

CREATE INDEX idx_orders_user_time ON orders(user_id, placed_at DESC);
CREATE INDEX idx_orders_status    ON orders(status) WHERE status IN ('pending','open');

CREATE TABLE positions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    mode            VARCHAR(8) NOT NULL,            -- 'paper' | 'live'
    side            VARCHAR(8) NOT NULL,            -- 'LONG' | 'SHORT'
    quantity        INT NOT NULL,
    avg_entry_price NUMERIC(12, 4) NOT NULL,
    current_sl      NUMERIC(12, 4),
    current_tp      NUMERIC(12, 4),
    trail_state     VARCHAR(16) NOT NULL DEFAULT 'none',
                                                    -- 'none' | 'breakeven' | 'trailing_1' | 'trailing_2'
    unrealized_pnl  NUMERIC(14, 2),                 -- updated on every tick for live, periodically for paper
    realized_pnl    NUMERIC(14, 2) DEFAULT 0,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    signal_id       UUID REFERENCES signals(id),
    journal_id      UUID                            -- back-ref to journal entry (set after close)
);

CREATE INDEX idx_positions_user_open ON positions(user_id) WHERE closed_at IS NULL;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TRADING JOURNAL                                                         │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    signal_id       UUID REFERENCES signals(id),
    position_id     UUID REFERENCES positions(id),
    entry_price     NUMERIC(12, 4) NOT NULL,
    exit_price      NUMERIC(12, 4),
    quantity        INT NOT NULL,
    strategy_used   VARCHAR(64),                    -- 'RRBO' | 'DC1' | 'DC2' | '9_25_AM' | …
    classification  VARCHAR(16),
    pnl_amount      NUMERIC(14, 2),
    pnl_pct         NUMERIC(7, 3),
    rr_achieved     NUMERIC(5, 2),

    emotion_before  VARCHAR(32),                    -- 'confident' | 'fearful' | 'fomo' | 'revenge'
    emotion_after   VARCHAR(32),
    followed_plan   BOOLEAN,                        -- did the user respect their setup?
    notes           TEXT,
    lesson_learned  TEXT,
    screenshot_urls TEXT[],                         -- entry/exit chart screenshots

    trade_date      DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_journal_user_date ON journal_entries(user_id, trade_date DESC);
CREATE INDEX idx_journal_strategy  ON journal_entries(strategy_used);
CREATE INDEX idx_journal_notes_trgm ON journal_entries USING gin(notes gin_trgm_ops);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ EXTERNAL PORTFOLIO (mutual funds, gold, SIPs)                           │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE external_holdings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    asset_type      VARCHAR(16) NOT NULL,
        -- 'mf' | 'stock' | 'gold' | 'sip' | 'fd' | 'bond' | 'crypto'
    asset_name      VARCHAR(255) NOT NULL,
    isin            VARCHAR(16),                    -- for MFs and bonds
    folio_number    VARCHAR(64),                    -- for MFs
    units           NUMERIC(18, 6),
    avg_cost        NUMERIC(14, 4),
    current_value   NUMERIC(14, 2),
    current_nav     NUMERIC(14, 4),                 -- for MFs/ETFs
    invested_amount NUMERIC(14, 2),
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          VARCHAR(32) NOT NULL,
        -- 'cas_import' | 'aa_finvu' | 'manual' | 'kite_holdings'
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ext_user_type ON external_holdings(user_id, asset_type);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ WATCHLISTS                                                              │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE watchlists (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(64) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, name)
);

CREATE TABLE watchlist_items (
    watchlist_id    BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    stock_id        BIGINT NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (watchlist_id, stock_id)
);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ ALERTS                                                                  │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stock_id        BIGINT NOT NULL REFERENCES stocks(id),
    alert_type      VARCHAR(32) NOT NULL,
        -- 'price_above' | 'price_below' | 'signal_generated' | 'pattern_detected'
    condition_value NUMERIC(12, 4),
    message         TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    triggered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_active ON alerts(stock_id) WHERE is_active = true;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ AUDIT LOG                                                               │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     BIGINT REFERENCES users(id),
    action      VARCHAR(64) NOT NULL,               -- 'order_placed' | 'login' | 'mode_changed' | …
    entity_type VARCHAR(32),                        -- 'order' | 'signal' | 'user' | …
    entity_id   VARCHAR(64),
    payload     JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_user_time ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_action    ON audit_log(action, created_at DESC);


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ UTILITY: updated_at trigger                                             │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE OR REPLACE FUNCTION update_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at column
CREATE TRIGGER trg_users_updated   BEFORE UPDATE ON users          FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_stocks_updated  BEFORE UPDATE ON stocks         FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_journal_updated BEFORE UPDATE ON journal_entries FOR EACH ROW EXECUTE FUNCTION update_timestamp();
