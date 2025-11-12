# 2025-11-11 – Engagement mix gating

We replaced the old `TREND_MIN_LIKES`/`TREND_MIN_RESPONSES` gates with a single
engagement-mix threshold that adapts to each author’s historical reach.

## What changed

- Ranking now checks the combined likes + reposts + replies count instead of
  requiring separate minimums.
- The required engagement scales relative to the author’s typical engagement.
  Smaller accounts need fewer total interactions; larger accounts need more.
- New environment variables:
  - `TREND_MIN_ENGAGEMENT` (default `20`) – baseline engagement sum required.
  - `TREND_AUTHOR_SCALE_MIN` (default `0.5`) – how far the requirement can drop
    for small authors (e.g., `0.5 * baseline = 10` interactions).
  - `TREND_AUTHOR_SCALE_MAX` (default `2.5`) – how far the requirement can grow
    for large authors (e.g., `2.5 * baseline = 50` interactions).
- The previous `TREND_MIN_LIKES` and `TREND_MIN_RESPONSES` env vars are now
  ignored. You can remove them after updating your `.env`.

## Action items

1. Add the new variables to your environment (or rely on defaults):
   ```env
   TREND_MIN_ENGAGEMENT=20
   TREND_AUTHOR_SCALE_MIN=0.5
   TREND_AUTHOR_SCALE_MAX=2.5
   ```
2. Remove legacy `TREND_MIN_LIKES` / `TREND_MIN_RESPONSES` entries.
3. Restart the backend/worker so the new settings take effect and rerun one
   ingest+rank cycle to repopulate thresholds.
