-- Runs once on first container creation, before any application connects.
-- Enables the extensions our schema will depend on.

-- TimescaleDB: turns plain Postgres tables into hypertables (time-partitioned)
-- for storing OHLCV candles efficiently. A 5-year history of Nifty50 1-min
-- candles is ~50 million rows; a hypertable handles this with sub-millisecond
-- range queries thanks to chunk pruning.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- pg_trgm: trigram-based fuzzy text search. Used for stock symbol/name
-- autocomplete ("rel" → RELIANCE, RELINFRA, etc.) and journal search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- uuid-ossp: generate UUIDs server-side for primary keys where we want
-- non-sequential IDs (signals, journal entries, audit log).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgcrypto: bcrypt/sha for any DB-level hashing if needed
-- (app-level bcrypt still primary, this is fallback/utility).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Confirm everything loaded.
DO $$
BEGIN
    RAISE NOTICE 'Extensions loaded: timescaledb=%, pg_trgm=%, uuid-ossp=%, pgcrypto=%',
        (SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'),
        (SELECT extversion FROM pg_extension WHERE extname = 'pg_trgm'),
        (SELECT extversion FROM pg_extension WHERE extname = 'uuid-ossp'),
        (SELECT extversion FROM pg_extension WHERE extname = 'pgcrypto');
END $$;
