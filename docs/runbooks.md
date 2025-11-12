# Operations Runbooks

Use these procedures to diagnose and resolve production issues.

## Contents
1. [Ingestion Failures](#ingestion-failures)
2. [Real-time Stream Issues](#real-time-stream-issues)
3. [Telegram Alert Problems](#telegram-alert-problems)
4. [Scheduler / Job Failures](#scheduler--job-failures)
5. [API Error Spikes](#api-error-spikes)
6. [Database Retention & Archival](#database-retention--archival)
7. [Prometheus & Grafana](#prometheus--grafana)

---

## Ingestion Failures
**Symptoms:** /health shows worker.ok=false, /metrics 	rendspark_ingest_items_total flatlines, or logs contain ingest errors.

1. Check worker logs
   `ash
   docker compose logs worker --tail 200
   `
2. Verify credentials
   - Ensure X_BEARER_TOKEN, REDDIT_* present and valid.
   - Check rate limits (X) or API bans.
3. Manual run
   `ash
   curl -X POST http://localhost:9000/scheduler/run \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"job_id": "ingest_rank"}'
   `
4. Fallback
   - Temporarily set X_INGEST_ENABLED=false or REDDIT_INGEST_ENABLED=false to isolate source.
   - Use /ingest/audit to confirm recent ingest rows.

Escalate to data team if credentials and connectivity are correct and job still fails.

## Real-time Stream Issues
**Symptoms:** No new posts despite X_STREAM_ENABLED=true.

1. Confirm stream rules: GET /stream/rules.
2. Check worker logs for stream errors.
3. Verify X Elevated access (developer portal) and token freshness.
4. Disable with X_STREAM_ENABLED=false and restart worker (docker compose restart worker) if flooding errors.
5. Document downtime in incident log.

## Telegram Alert Problems
**Symptoms:** Expect alerts but none arrive.

1. Check /health ? services.telegram.ok.
2. Inspect logs for 	elegram.sent or warnings.
3. Manual test:
   `ash
   python - <<'PY'
   from trend_spark_ai.notifier import send_telegram_message
   print(send_telegram_message('Trend? test alert', category='manual_test'))
   PY
   `
4. If failing:
   - Validate TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.
   - Confirm bot has access to the chat.
   - Set ENABLE_REALTIME_ALERTS=false to silence alerts until resolved.

## Scheduler / Job Failures
**Symptoms:** Repeated job errors, Telegram job alerts.

1. /scheduler/jobs for paused or missing next run.
2. Check job_runs table (or metrics) for failure details.
3. Review worker logs for stack traces.
4. After fix, trigger manually via /scheduler/run.
5. Pause job temporarily with POST /scheduler/toggle (payload { "job_id": "ingest_rank", "action": "pause" }).

## API Error Spikes
**Symptoms:** Telegram API errors spiking alert, 5xx surge.

1. Inspect API logs (equest.completed).
2. Identify failing endpoint from alert payload.
3. Check dependencies (DB, external APIs).
4. Roll back recent deploy if necessary.
5. Alert auto-resolves once errors drop below threshold.

## Database Retention & Archival
**Goal:** keep live DB lean while preserving history.

1. Retention windows
   - Posts/Ingest Audit: 30–45 days.
   - Notifications: 90 days.
2. Archive workflow (until automated job lands):
   - Export rows older than window to CSV/Parquet (S3 bucket 	rendai-archive), record checksum.
   - Delete exported rows in batches (1k per transaction).
   - Vacuum: SQLite VACUUM; Postgres VACUUM ANALYZE weekly.
3. Track archives in rchive_manifests (planned) or ops log.

## Prometheus & Grafana
1. Prometheus UI: http://localhost:9090
   - Example query: ate(trendspark_ingest_items_total[5m])
   - Verify worker metrics: histogram_quantile(0.95, sum by (le,job)(rate(trendspark_job_duration_seconds_bucket[5m])))
2. Grafana: http://localhost:3000 (admin/admin)
   - Add data source: http://prometheus:9090
   - Dashboards: ingest overview, alert delivery, OpenAI usage, job duration.
3. Alerts: configure Grafana rules ? Slack/Telegram when backlog, errors, or ingestion stalls.
4. Retention: adjust Prometheus --storage.tsdb.retention.time in docker-compose.yml to manage disk usage.

Keep this runbook updated as new failure modes and workflows emerge.

