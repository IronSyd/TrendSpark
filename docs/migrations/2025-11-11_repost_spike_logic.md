# 2025-11-11 – Repost spike + profile priority bonuses

> **Update (2025-11-12):** The repost spike bonus has since been removed. The
> schema alterations below were retained, but no runtime logic reads those
> columns anymore. You can drop the `REPOST_SPIKE_*` env vars if you previously
> added them.

To support rate-of-change alerts we now track the previous repost count for
each post and detect “spikes” (reposts doubling inside a short window). Those
spikes add a temporary virality bonus so low-like tweets can still surface when
their repost velocity explodes. We also prioritize tweets that come from
watchlisted handles *and* mention your growth profile keywords by giving them a
small virality bump.

## Schema changes

Run the following against every environment (already applied to dev):

```sql
ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS prev_repost_count INTEGER,
    ADD COLUMN IF NOT EXISTS prev_metrics_at TIMESTAMP;
```

## New environment variables

```env
PROFILE_MATCH_BONUS=0.1          # Extra virality when watchlist handle + keyword align
X_TRENDS_WOEID=1                 # (Optional) Which location's trending list to use
TRENDING_HASHTAG_BONUS=0.08      # Bonus when a post uses one of the trending hashtags
```

Optional, only if you have elevated X API credentials (OAuth 1.1):

```env
X_CONSUMER_KEY=
X_CONSUMER_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=
```

Without those keys the app will skip the external trending list and rely purely
on growth-profile keywords/watchlist as before.

After updating the env, restart the backend + worker so the scheduler loads the
new settings. Trigger one `ingest + rank` cycle to seed the baseline repost
snapshots (only relevant if you still rely on the historical columns).
