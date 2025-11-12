# Migration: Trending Candidate Confirmation

Date: 2025-11-09

This change introduces a `trending_candidate_since` timestamp on `posts` so we can track when a post first crosses the virality + engagement floor before it is promoted to a confirmed trend. Alerts now only fire after the candidate has stayed above the threshold for the configured confirmation window.

## Postgres

```sql
ALTER TABLE posts
    ADD COLUMN trending_candidate_since TIMESTAMPTZ NULL;
CREATE INDEX ix_posts_candidate_since
    ON posts (trending_candidate_since);
```

## SQLite (dev)

SQLite cannot add indexed columns in a single statement, so run:

```sql
ALTER TABLE posts ADD COLUMN trending_candidate_since TEXT;
CREATE INDEX ix_posts_candidate_since ON posts (trending_candidate_since);
```

## Backfill

Existing rows can leave `trending_candidate_since` null. After deploying the new ranking code, rerun at least one `ingest + rank` cycle so the candidate timestamps are populated naturally.

## Configuration

New environment variables (with defaults):

```
TREND_MIN_LIKES=5
TREND_MIN_RESPONSES=3
TREND_CONFIRMATION_MINUTES=10
```

Tune these to control the engagement floor and how long a candidate must stay hot before it is considered trending.
