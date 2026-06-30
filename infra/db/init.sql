-- ─────────────────────────────────────────────────────────────────────────
-- PDRP — PostgreSQL Init Script
-- Runs once on first container start.
-- TimescaleDB extension is enabled here.
-- Full schema via Alembic migrations (Sprint 2).
-- ─────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fast text search on table names

-- Signal successful init
DO $$
BEGIN
    RAISE NOTICE 'PDRP database initialized with TimescaleDB, uuid-ossp, pg_trgm';
END
$$;
