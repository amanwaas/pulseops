-- ============================================================================
-- PulseOps: Production PostgreSQL 16 Schema for Neon (Serverless Postgres)
-- ============================================================================

-- Ensure uuid-ossp or pgcrypto extension is available for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean drop for idempotency if running fresh migration
-- (In production, use standard Alembic migrations)
DROP TABLE IF EXISTS health_logs CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
DROP TABLE IF EXISTS alert_configs CASCADE;
DROP TABLE IF EXISTS health_targets CASCADE;
DROP TABLE IF EXISTS deployments CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Users Table (Authentication & RBAC)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'developer', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- ----------------------------------------------------------------------------
-- 2. Projects Table (5–20 Monitored Microservices / Applications)
-- ----------------------------------------------------------------------------
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    repo_url VARCHAR(500) NOT NULL,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('github', 'gitlab')),
    webhook_secret_encrypted TEXT NOT NULL, -- AES-256-GCM encrypted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_slug ON projects(slug);

-- ----------------------------------------------------------------------------
-- 3. Deployments Table (CI/CD Deployment History)
-- ----------------------------------------------------------------------------
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    environment VARCHAR(50) NOT NULL CHECK (environment IN ('development', 'testing', 'staging', 'production')),
    commit_sha VARCHAR(64) NOT NULL,
    commit_message TEXT,
    branch VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    status VARCHAR(50) NOT NULL CHECK (status IN ('queued', 'in_progress', 'success', 'failure', 'cancelled')),
    duration_seconds INTEGER DEFAULT 0,
    pipeline_id VARCHAR(255),
    pipeline_url VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deployments_project_env_created ON deployments(project_id, environment, created_at DESC);
CREATE INDEX idx_deployments_commit_sha ON deployments(commit_sha);
CREATE INDEX idx_deployments_status ON deployments(status);

-- ----------------------------------------------------------------------------
-- 4. Health Targets Table (Active Monitoring Endpoints)
-- ----------------------------------------------------------------------------
CREATE TABLE health_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    environment VARCHAR(50) NOT NULL CHECK (environment IN ('development', 'testing', 'staging', 'production')),
    endpoint_url VARCHAR(1000) NOT NULL,
    check_interval_seconds INTEGER NOT NULL DEFAULT 60 CHECK (check_interval_seconds >= 10),
    timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds >= 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_status VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN' CHECK (last_status IN ('UNKNOWN', 'UP', 'DOWN', 'DEGRADED')),
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_env_endpoint UNIQUE (project_id, environment, endpoint_url)
);

CREATE INDEX idx_health_targets_active ON health_targets(is_active);
CREATE INDEX idx_health_targets_project ON health_targets(project_id);

-- ----------------------------------------------------------------------------
-- 5. Health Logs Table (High-Frequency Latency & Status Time-Series)
-- ----------------------------------------------------------------------------
CREATE TABLE health_logs (
    id BIGSERIAL PRIMARY KEY,
    target_id UUID NOT NULL REFERENCES health_targets(id) ON DELETE CASCADE,
    status_code INTEGER,
    latency_ms DOUBLE PRECISION NOT NULL,
    is_up BOOLEAN NOT NULL,
    error_message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index for fast time-range querying per target (ECharts Latency graphs)
CREATE INDEX idx_health_logs_target_checked ON health_logs(target_id, checked_at DESC);
-- Single index on checked_at for rapid 30-day retention pruning
CREATE INDEX idx_health_logs_checked_at ON health_logs(checked_at);

-- ----------------------------------------------------------------------------
-- 6. Alert Configurations Table (Slack, Teams, Email, Generic Webhook)
-- ----------------------------------------------------------------------------
CREATE TABLE alert_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    channel_type VARCHAR(50) NOT NULL CHECK (channel_type IN ('slack', 'teams', 'email', 'webhook')),
    destination_url_encrypted TEXT NOT NULL, -- AES-256-GCM encrypted
    notify_on_deployment_fail BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_health_fail BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alert_configs_project ON alert_configs(project_id);

-- ----------------------------------------------------------------------------
-- 7. Incidents Table (State Machine Failure Tracking & Recovery)
-- ----------------------------------------------------------------------------
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id UUID NOT NULL REFERENCES health_targets(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    failure_reason TEXT NOT NULL,
    consecutive_failures INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incidents_target_status ON incidents(target_id, status);
CREATE INDEX idx_incidents_started_at ON incidents(started_at DESC);

-- ----------------------------------------------------------------------------
-- Helper Functions & Trigger for auto-updating updated_at timestamp
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER trg_health_targets_updated_at
BEFORE UPDATE ON health_targets
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
