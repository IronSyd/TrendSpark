# Migration: Scheduler Configs Table

Date: 2025-11-08

This migration introduces the scheduler_configs table which stores runtime configuration for each scheduler job (Cron expression, parameters, concurrency limits, etc.).

## Postgres

`sql
CREATE TABLE scheduler_configs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    name VARCHAR(128),
    cron VARCHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 5,
    concurrency_limit INTEGER NOT NULL DEFAULT 1,
    lock_timeout_seconds INTEGER NOT NULL DEFAULT 300,
    parameters JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_scheduler_config_name_per_job
    ON scheduler_configs (job_id, name);

CREATE INDEX ix_scheduler_enabled_priority
    ON scheduler_configs (enabled, priority);
`

## SQLite (dev)

SQLite lacks certain features, so recreate the schema manually:

`sql
CREATE TABLE scheduler_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    name TEXT,
    cron TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 5,
    concurrency_limit INTEGER NOT NULL DEFAULT 1,
    lock_timeout_seconds INTEGER NOT NULL DEFAULT 300,
    parameters TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX uq_scheduler_config_name_per_job
    ON scheduler_configs (job_id, name);

CREATE INDEX ix_scheduler_enabled_priority
    ON scheduler_configs (enabled, priority);
`

## Backfill

1. Insert baseline configs for existing jobs (ingestion, ranking, alerts). Example:

`sql
INSERT INTO scheduler_configs (job_id, name, cron, parameters)
VALUES
  ('job_ingest', 'default', '*/5 * * * *', '{"max_x": 20}'),
  ('job_rank', 'default', '*/10 * * * *', '{}');
`

2. Update workers to read from scheduler_configs before deploying.

3. After validation, remove any hard-coded schedules from the worker configuration.
## 2025-11-08 Update

Extended the migration to include:

1. job_runs.config_id (nullable FK to scheduler_configs) and job_runs.correlation_id for richer audit trails.
2. scheduler_locks table to coordinate concurrency across multiple worker instances.

### Postgres
`sql
ALTER TABLE job_runs ADD COLUMN config_id INTEGER REFERENCES scheduler_configs(id);
ALTER TABLE job_runs ADD COLUMN correlation_id VARCHAR(64);
CREATE INDEX ix_job_runs_config ON job_runs(config_id);

CREATE TABLE scheduler_locks (
    id SERIAL PRIMARY KEY,
    config_id INTEGER NOT NULL REFERENCES scheduler_configs(id) ON DELETE CASCADE,
    lock_token VARCHAR(64) NOT NULL UNIQUE,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_scheduler_lock_expiry CHECK (expires_at > acquired_at)
);
CREATE INDEX ix_scheduler_locks_active ON scheduler_locks(config_id, expires_at);
`

### SQLite
`sql
ALTER TABLE job_runs ADD COLUMN config_id INTEGER;
ALTER TABLE job_runs ADD COLUMN correlation_id TEXT;
CREATE INDEX ix_job_runs_config ON job_runs(config_id);

CREATE TABLE scheduler_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL REFERENCES scheduler_configs(id) ON DELETE CASCADE,
    lock_token TEXT NOT NULL UNIQUE,
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
CREATE INDEX ix_scheduler_locks_active ON scheduler_locks(config_id, expires_at);
`

After migration, deploy new worker code that manages these locks before enabling multiple scheduler instances.
