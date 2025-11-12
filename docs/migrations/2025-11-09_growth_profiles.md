# Migration: Growth Profiles & Scheduler Linking

Date: 2025-11-09

This migration turns the existing `growth_config` table into a reusable set of **growth profiles** and lets each scheduler config target a specific profile. After applying it you can run multiple ingest/ranking jobs concurrently with different keyword/watchlist bundles.

## Postgres

```sql
ALTER TABLE growth_config
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN name VARCHAR(128) NOT NULL DEFAULT 'Default profile',
    ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE scheduler_configs
    ADD COLUMN growth_profile_id INTEGER REFERENCES growth_config(id);

CREATE INDEX ix_growth_config_active ON growth_config(is_active);
CREATE INDEX ix_growth_config_default ON growth_config(is_default);
CREATE INDEX ix_scheduler_growth_profile ON scheduler_configs(growth_profile_id);
```

## SQLite (dev)

SQLite cannot `ALTER TABLE ... ADD COLUMN` with defaults for multiple columns easily, so recreate the table:

```sql
CREATE TABLE growth_config_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    name TEXT NOT NULL DEFAULT 'Default profile',
    is_default INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    niche TEXT,
    keywords TEXT,
    watchlist TEXT
);

INSERT INTO growth_config_new (id, created_at, updated_at, name, is_default, is_active, niche, keywords, watchlist)
SELECT id, created_at, created_at, 'Default profile', 0, 1, niche, keywords, watchlist
FROM growth_config;

DROP TABLE growth_config;
ALTER TABLE growth_config_new RENAME TO growth_config;

CREATE INDEX ix_growth_config_active ON growth_config(is_active);
CREATE INDEX ix_growth_config_default ON growth_config(is_default);

ALTER TABLE scheduler_configs ADD COLUMN growth_profile_id INTEGER REFERENCES growth_config(id);
CREATE INDEX ix_scheduler_growth_profile ON scheduler_configs(growth_profile_id);
```

## Backfill Steps

1. Pick the profile you want as the default (typically the most recent row) and run:
   ```sql
   UPDATE growth_config SET is_default = TRUE WHERE id = <chosen_id>;
   UPDATE growth_config SET name = 'Default profile' WHERE id = <chosen_id> AND (name IS NULL OR name = '');
   ```
2. Point existing scheduler configs at that default profile:
   ```sql
   UPDATE scheduler_configs SET growth_profile_id = <chosen_id> WHERE growth_profile_id IS NULL;
   ```
3. Deploy the new application code (API + worker) and restart the worker so it reloads scheduler configs.

After deploying you can create additional profiles through the API/CLI/UI and assign them to individual scheduler jobs.
