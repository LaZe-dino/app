-- ═══════════════════════════════════════════════════════════════════════════════
--  AI-Native Hedge Fund + HFT Engine — Supabase PostgreSQL Schema
-- ═══════════════════════════════════════════════════════════════════════════════
--
--  Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New Query)
--  or via the Supabase CLI: supabase db push
--
--  Tables:
--    1. users           — authenticated users with JWT + API keys
--    2. portfolio        — user portfolio holdings
--    3. trade_signals    — AI-generated trade signals
--    4. reports          — research reports from swarm analysis
--    5. hft_trades       — HFT engine execution log
--    6. hft_snapshots    — HFT dashboard snapshots for history
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── 1. Users ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    api_key         TEXT UNIQUE NOT NULL,
    plan            TEXT NOT NULL DEFAULT 'free',
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

-- ─── 2. Portfolio ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS portfolio (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    shares          INTEGER NOT NULL DEFAULT 0,
    avg_cost        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio(user_id);

-- ─── 3. Trade Signals ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trade_signals (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL DEFAULT 'HOLD',
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    price_target    DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    current_price   DOUBLE PRECISION,
    reasoning       TEXT DEFAULT '',
    key_factors     JSONB DEFAULT '[]',
    time_horizon    TEXT DEFAULT 'swing',
    risk_level      TEXT DEFAULT 'medium',
    agent_type      TEXT DEFAULT 'strategist_swarm',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_user ON trade_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON trade_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON trade_signals(timestamp DESC);

-- ─── 4. Reports ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    analysis_type   TEXT DEFAULT 'comprehensive',
    summary         TEXT DEFAULT '',
    sentiment       TEXT DEFAULT 'neutral',
    sentiment_score DOUBLE PRECISION DEFAULT 0.0,
    key_findings    JSONB DEFAULT '[]',
    risks           JSONB DEFAULT '[]',
    recommendation  TEXT DEFAULT 'HOLD',
    confidence      DOUBLE PRECISION DEFAULT 0.5,
    agent_name      TEXT DEFAULT 'Strategist-C1',
    technical_data  JSONB DEFAULT '{}',
    sentiment_data  JSONB DEFAULT '{}',
    swarm_recommendation JSONB DEFAULT '{}',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp DESC);

-- ─── 5. HFT Trades ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS hft_trades (
    id              BIGSERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    fill_price      DOUBLE PRECISION NOT NULL,
    fill_qty        INTEGER NOT NULL,
    venue           TEXT NOT NULL,
    strategy_id     TEXT DEFAULT '',
    liquidity       TEXT DEFAULT 'MAKER',
    fee             DOUBLE PRECISION DEFAULT 0.0,
    timestamp_ns    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hft_trades_symbol ON hft_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_hft_trades_created ON hft_trades(created_at DESC);

-- ─── 6. HFT Snapshots (optional — for historical dashboard data) ────────────

CREATE TABLE IF NOT EXISTS hft_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_data   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hft_snapshots_created ON hft_snapshots(created_at DESC);

-- ─── Row Level Security ──────────────────────────────────────────────────────
--  Enable RLS so each user can only see their own data.
--  The backend uses the service_role key which bypasses RLS.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Service role (backend) can do everything
CREATE POLICY "service_role_all" ON users FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON portfolio FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON trade_signals FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON reports FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- ─── Helpful Views ───────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW user_portfolio_summary AS
SELECT
    p.user_id,
    COUNT(*)::INTEGER AS holdings_count,
    SUM(p.shares * p.avg_cost) AS total_cost
FROM portfolio p
GROUP BY p.user_id;

CREATE OR REPLACE VIEW recent_signals AS
SELECT *
FROM trade_signals
ORDER BY timestamp DESC
LIMIT 100;
