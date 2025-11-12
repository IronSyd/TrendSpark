# Migration: Drop `performance_metrics` Table

Date: 2025-11-10

The historical “Performance” surface was removed from both frontend and backend.
It no longer reads or writes any data, so the `performance_metrics` table can be
deleted to keep the database lean.

## Postgres

```sql
DROP TABLE IF EXISTS performance_metrics;
```

No other tables reference `performance_metrics`, so no cascade is required.

## SQLite (dev)

```sql
DROP TABLE IF EXISTS performance_metrics;
```

## Notes

- Run the statement in every environment (dev/staging/prod) after deploying the
  code that removed `/performance/log*` endpoints.
- There is no backfill needed; the table is obsolete.
