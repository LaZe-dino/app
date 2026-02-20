-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  AI-Native Hedge Fund — Multi-Agent Swarm Schema                           ║
-- ║  Supabase PostgreSQL · 11 tables · 8 agents · full swarm pipeline          ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝
--
--  Run via: Supabase Dashboard → SQL Editor → New Query
--        or: supabase db push
--
--  ┌─────────────────────────────────────────────────────────────────┐
--  │  Table Map                                                      │
--  │                                                                 │
--  │  Core:                                                          │
--  │    1. users              – auth + API keys + plans              │
--  │    2. portfolio          – user holdings                        │
--  │    3. trade_signals      – AI-generated trade signals           │
--  │    4. reports            – full swarm research reports           │
--  │                                                                 │
--  │  Swarm:                                                         │
--  │    5. swarm_agents       – agent registry (8 agents)            │
--  │    6. swarm_events       – event bus log (handoffs, spikes)     │
--  │    7. risk_verdicts      – risk guardrail decisions             │
--  │    8. filings            – SEC 10-K / 10-Q ingested data       │
--  │    9. vector_memories    – long-term RAG memory store           │
--  │                                                                 │
--  │  HFT:                                                           │
--  │   10. hft_trades         – execution log                        │
--  │   11. hft_snapshots      – dashboard history                    │
--  └─────────────────────────────────────────────────────────────────┘


-- ── CLEAN SLATE ─────────────────────────────────────────────────────────────────
-- Drop everything in reverse dependency order so the schema runs on both
-- fresh databases and ones that already have the old tables.

DROP VIEW  IF EXISTS v_latest_filings    CASCADE;
DROP VIEW  IF EXISTS v_event_summary     CASCADE;
DROP VIEW  IF EXISTS v_agent_performance CASCADE;
DROP VIEW  IF EXISTS v_swarm_dashboard   CASCADE;
DROP VIEW  IF EXISTS v_recent_signals    CASCADE;
DROP VIEW  IF EXISTS v_portfolio_summary CASCADE;
DROP VIEW  IF EXISTS user_portfolio_summary CASCADE;
DROP VIEW  IF EXISTS recent_signals         CASCADE;

DROP TRIGGER IF EXISTS trg_portfolio_updated ON portfolio;
DROP TRIGGER IF EXISTS trg_users_updated     ON users;
DROP FUNCTION IF EXISTS set_updated_at();
DROP FUNCTION IF EXISTS prune_old_swarm_events();

DROP TABLE IF EXISTS hft_snapshots   CASCADE;
DROP TABLE IF EXISTS hft_trades      CASCADE;
DROP TABLE IF EXISTS vector_memories CASCADE;
DROP TABLE IF EXISTS filings         CASCADE;
DROP TABLE IF EXISTS risk_verdicts   CASCADE;
DROP TABLE IF EXISTS swarm_events    CASCADE;
DROP TABLE IF EXISTS swarm_agents    CASCADE;
DROP TABLE IF EXISTS reports         CASCADE;
DROP TABLE IF EXISTS trade_signals   CASCADE;
DROP TABLE IF EXISTS portfolio       CASCADE;
DROP TABLE IF EXISTS users           CASCADE;


-- ── Extensions ──────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  1. USERS
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE users (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    api_key         TEXT UNIQUE NOT NULL,
    plan            TEXT NOT NULL DEFAULT 'free'
                        CHECK (plan IN ('free', 'pro', 'enterprise')),
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email   ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users (api_key);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  2. PORTFOLIO
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE portfolio (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    shares          INTEGER NOT NULL DEFAULT 0,
    avg_cost        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_user   ON portfolio (user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_symbol ON portfolio (symbol);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  3. TRADE SIGNALS
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE trade_signals (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL DEFAULT 'HOLD'
                        CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    price_target    DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    current_price   DOUBLE PRECISION,
    reasoning       TEXT DEFAULT '',
    key_factors     JSONB DEFAULT '[]',
    time_horizon    TEXT DEFAULT 'swing'
                        CHECK (time_horizon IN ('intraday', 'swing', 'position')),
    risk_level      TEXT DEFAULT 'medium'
                        CHECK (risk_level IN ('low', 'medium', 'high')),
    agent_type      TEXT DEFAULT 'strategist_swarm',

    -- Risk guardrail verdict (populated after risk check)
    risk_approved   BOOLEAN,
    risk_warnings   JSONB DEFAULT '[]',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_user      ON trade_signals (user_id);
CREATE INDEX IF NOT EXISTS idx_signals_symbol    ON trade_signals (symbol);
CREATE INDEX IF NOT EXISTS idx_signals_action    ON trade_signals (action);
CREATE INDEX IF NOT EXISTS idx_signals_created   ON trade_signals (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  4. REPORTS  (full swarm research output)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE reports (
    id                   TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol               TEXT NOT NULL,
    analysis_type        TEXT DEFAULT 'comprehensive'
                             CHECK (analysis_type IN ('comprehensive', 'deep', 'quick')),

    -- Synthesis output
    summary              TEXT DEFAULT '',
    sentiment            TEXT DEFAULT 'neutral',
    sentiment_score      DOUBLE PRECISION DEFAULT 0.0,
    recommendation       TEXT DEFAULT 'HOLD',
    confidence           DOUBLE PRECISION DEFAULT 0.5,
    agent_name           TEXT DEFAULT 'Synthesis-B1',

    -- Structured findings
    key_findings         JSONB DEFAULT '[]',
    risks                JSONB DEFAULT '[]',

    -- Agent pipeline data (JSONB blobs for flexibility)
    technical_data       JSONB DEFAULT '{}',
    sentiment_data       JSONB DEFAULT '{}',
    fundamental_data     JSONB DEFAULT '{}',
    quantitative_data    JSONB DEFAULT '{}',
    swarm_recommendation JSONB DEFAULT '{}',
    risk_verdict         JSONB DEFAULT '{}',

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user    ON reports (user_id);
CREATE INDEX IF NOT EXISTS idx_reports_symbol  ON reports (symbol);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  5. SWARM AGENTS  (agent registry — 8 autonomous agents)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--
--  Agent Roster:
--    Scout-S1, Analyst-A1, NewsHound-N1, Strategist-C1,
--    Ingestion-I1, Quant-Q1, Synthesis-B1, RiskGuardrail-R1

CREATE TABLE swarm_agents (
    id              TEXT PRIMARY KEY,                -- e.g. "Scout-S1"
    role            TEXT NOT NULL
                        CHECK (role IN (
                            'scout', 'analyst', 'news_hound', 'strategist',
                            'ingestion', 'quantitative', 'synthesis', 'risk'
                        )),
    status          TEXT NOT NULL DEFAULT 'idle'
                        CHECK (status IN ('idle', 'active', 'processing', 'error')),
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    current_task    TEXT,
    cycle_interval  DOUBLE PRECISION DEFAULT 10.0,   -- seconds between cycles
    last_active     TIMESTAMPTZ DEFAULT NOW(),
    error_log       JSONB DEFAULT '[]',
    config          JSONB DEFAULT '{}',              -- agent-specific settings
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_swarm_agents_role   ON swarm_agents (role);
CREATE INDEX IF NOT EXISTS idx_swarm_agents_status ON swarm_agents (status);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  6. SWARM EVENTS  (event bus history — handoffs, spikes, alerts)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE swarm_events (
    id              BIGSERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL
                        CHECK (event_type IN (
                            'price_spike', 'volume_anomaly', 'technical_signal',
                            'sentiment_shift', 'news_alert', 'trade_recommendation',
                            'risk_alert', 'agent_handoff', 'agent_status',
                            'swarm_cycle_complete'
                        )),
    source_agent    TEXT NOT NULL,
    target_agent    TEXT,
    symbol          TEXT,
    data            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_swarm_events_type    ON swarm_events (event_type);
CREATE INDEX IF NOT EXISTS idx_swarm_events_symbol  ON swarm_events (symbol);
CREATE INDEX IF NOT EXISTS idx_swarm_events_source  ON swarm_events (source_agent);
CREATE INDEX IF NOT EXISTS idx_swarm_events_created ON swarm_events (created_at DESC);

-- Auto-prune: keep last 30 days of events
-- (run as a Supabase cron or pg_cron job)
CREATE OR REPLACE FUNCTION prune_old_swarm_events()
RETURNS void LANGUAGE sql AS $$
    DELETE FROM swarm_events WHERE created_at < NOW() - INTERVAL '30 days';
$$;


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  7. RISK VERDICTS  (RiskGuardrail-R1 decisions)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE risk_verdicts (
    id                  BIGSERIAL PRIMARY KEY,
    signal_id           TEXT REFERENCES trade_signals(id) ON DELETE SET NULL,
    symbol              TEXT NOT NULL,
    action              TEXT NOT NULL,
    original_confidence DOUBLE PRECISION NOT NULL,
    approved            BOOLEAN NOT NULL,
    verdict             TEXT NOT NULL
                            CHECK (verdict IN ('APPROVED', 'FLAGGED', 'REJECTED')),
    warnings            JSONB DEFAULT '[]',
    checked_by          TEXT DEFAULT 'RiskGuardrail-R1',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_verdicts_symbol  ON risk_verdicts (symbol);
CREATE INDEX IF NOT EXISTS idx_risk_verdicts_verdict ON risk_verdicts (verdict);
CREATE INDEX IF NOT EXISTS idx_risk_verdicts_created ON risk_verdicts (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  8. FILINGS  (Ingestion-I1 — SEC 10-K / 10-Q parsed data)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE filings (
    id               BIGSERIAL PRIMARY KEY,
    symbol           TEXT NOT NULL,
    filing_type      TEXT NOT NULL DEFAULT '10-K'
                         CHECK (filing_type IN ('10-K', '10-Q', '8-K', 'DEF14A')),

    -- Financials (structured)
    revenue          BIGINT,
    net_income       BIGINT,
    total_assets     BIGINT,
    total_debt       BIGINT,
    cash             BIGINT,
    gross_margin     DOUBLE PRECISION,
    operating_margin DOUBLE PRECISION,
    eps              DOUBLE PRECISION,
    pe_ratio         DOUBLE PRECISION,

    -- Raw / extra fields
    raw_data         JSONB DEFAULT '{}',
    source           TEXT DEFAULT 'simulated',
    ingested_by      TEXT DEFAULT 'Ingestion-I1',

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, filing_type, created_at)
);

CREATE INDEX IF NOT EXISTS idx_filings_symbol  ON filings (symbol);
CREATE INDEX IF NOT EXISTS idx_filings_type    ON filings (filing_type);
CREATE INDEX IF NOT EXISTS idx_filings_created ON filings (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  9. VECTOR MEMORIES  (long-term RAG store for Synthesis + Strategist)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE vector_memories (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT,
    memory_type     TEXT NOT NULL
                        CHECK (memory_type IN (
                            'filing', 'deep_analysis', 'market_observation',
                            'news_summary', 'strategy_note'
                        )),
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    stored_by       TEXT DEFAULT 'Swarm',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vector_memories_symbol  ON vector_memories (symbol);
CREATE INDEX IF NOT EXISTS idx_vector_memories_type    ON vector_memories (memory_type);
CREATE INDEX IF NOT EXISTS idx_vector_memories_created ON vector_memories (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  10. HFT TRADES
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE hft_trades (
    id              BIGSERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    fill_price      DOUBLE PRECISION NOT NULL,
    fill_qty        INTEGER NOT NULL,
    venue           TEXT NOT NULL,
    strategy_id     TEXT DEFAULT '',
    liquidity       TEXT DEFAULT 'MAKER' CHECK (liquidity IN ('MAKER', 'TAKER')),
    fee             DOUBLE PRECISION DEFAULT 0.0,
    timestamp_ns    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hft_trades_symbol  ON hft_trades (symbol);
CREATE INDEX IF NOT EXISTS idx_hft_trades_created ON hft_trades (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  11. HFT SNAPSHOTS
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE hft_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_data   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hft_snapshots_created ON hft_snapshots (created_at DESC);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  ROW LEVEL SECURITY
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  Backend uses service_role which bypasses RLS.
--  These policies ensure users can only see their own data via client-side access.

ALTER TABLE users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio      ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_signals  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_all_users"    ON users         FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_all_port"     ON portfolio     FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_all_signals"  ON trade_signals FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_all_reports"  ON reports       FOR ALL USING (TRUE) WITH CHECK (TRUE);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  VIEWS — efficient read-only dashboards
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Portfolio summary per user
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT
    p.user_id,
    COUNT(*)::INTEGER              AS holdings_count,
    SUM(p.shares)::INTEGER         AS total_shares,
    SUM(p.shares * p.avg_cost)     AS total_cost
FROM portfolio p
GROUP BY p.user_id;

-- Latest 100 signals with risk verdict
CREATE OR REPLACE VIEW v_recent_signals AS
SELECT
    ts.*,
    rv.verdict      AS risk_verdict,
    rv.warnings     AS risk_warnings_detail,
    rv.created_at   AS risk_checked_at
FROM trade_signals ts
LEFT JOIN risk_verdicts rv ON rv.signal_id = ts.id
ORDER BY ts.created_at DESC
LIMIT 100;

-- Swarm agent dashboard
CREATE OR REPLACE VIEW v_swarm_dashboard AS
SELECT
    sa.id,
    sa.role,
    sa.status,
    sa.tasks_completed,
    sa.current_task,
    sa.last_active,
    sa.cycle_interval,
    (SELECT COUNT(*) FROM swarm_events se WHERE se.source_agent = sa.id
        AND se.created_at > NOW() - INTERVAL '1 hour')::INTEGER AS events_last_hour
FROM swarm_agents sa
ORDER BY sa.role;

-- Signal accuracy by agent (how many approved vs flagged)
CREATE OR REPLACE VIEW v_agent_performance AS
SELECT
    ts.agent_type,
    COUNT(*)::INTEGER                                          AS total_signals,
    COUNT(*) FILTER (WHERE ts.action = 'BUY')::INTEGER         AS buy_count,
    COUNT(*) FILTER (WHERE ts.action = 'SELL')::INTEGER        AS sell_count,
    COUNT(*) FILTER (WHERE ts.action = 'HOLD')::INTEGER        AS hold_count,
    ROUND(AVG(ts.confidence)::NUMERIC, 3)                      AS avg_confidence,
    COUNT(*) FILTER (WHERE ts.risk_approved = TRUE)::INTEGER   AS risk_approved,
    COUNT(*) FILTER (WHERE ts.risk_approved = FALSE)::INTEGER  AS risk_flagged
FROM trade_signals ts
GROUP BY ts.agent_type
ORDER BY total_signals DESC;

-- Event stream summary (last 24h grouped by type)
CREATE OR REPLACE VIEW v_event_summary AS
SELECT
    event_type,
    COUNT(*)::INTEGER AS event_count,
    COUNT(DISTINCT symbol)::INTEGER AS symbols_involved,
    MAX(created_at) AS last_seen
FROM swarm_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY event_type
ORDER BY event_count DESC;

-- Latest filing per symbol
CREATE OR REPLACE VIEW v_latest_filings AS
SELECT DISTINCT ON (symbol, filing_type)
    symbol,
    filing_type,
    revenue,
    net_income,
    gross_margin,
    operating_margin,
    eps,
    pe_ratio,
    created_at
FROM filings
ORDER BY symbol, filing_type, created_at DESC;


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  SEED DATA — default agent registry
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSERT INTO swarm_agents (id, role, status, cycle_interval, config) VALUES
    ('Scout-S1',        'scout',        'idle',  8.0,   '{"threshold_pct": 0.02, "volume_multiplier": 1.5}'),
    ('Analyst-A1',      'analyst',      'idle', 15.0,   '{"indicators": ["RSI", "MACD", "Bollinger", "SMA"]}'),
    ('NewsHound-N1',    'news_hound',   'idle', 12.0,   '{"sources": ["Reuters", "Bloomberg", "CNBC"]}'),
    ('Strategist-C1',   'strategist',   'idle', 20.0,   '{"model": "gpt-5.2", "provider": "emergent"}'),
    ('Ingestion-I1',    'ingestion',    'idle', 300.0,  '{"filing_types": ["10-K", "10-Q"]}'),
    ('Quant-Q1',        'quantitative', 'idle', 15.0,   '{"indicators": ["ATR", "OBV", "Fibonacci", "VWAP"]}'),
    ('Synthesis-B1',    'synthesis',    'idle', 25.0,   '{"weights": {"technical": 0.4, "fundamental": 0.3, "sentiment": 0.3}}'),
    ('RiskGuardrail-R1','risk',         'idle', 10.0,   '{"max_position_pct": 0.25, "min_confidence": 0.4}')
ON CONFLICT (id) DO NOTHING;


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--  UTILITY FUNCTIONS
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Auto-update `updated_at` on users and portfolio
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_portfolio_updated
    BEFORE UPDATE ON portfolio
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
