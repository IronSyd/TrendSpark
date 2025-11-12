from __future__ import annotations

from typing import Mapping

from prometheus_client import Counter, Gauge, Histogram


INGEST_ITEMS_TOTAL = Counter(
    "trendspark_ingest_items_total",
    "Number of posts ingested by source/platform.",
    labelnames=("source",),
)

INGEST_CYCLES_TOTAL = Counter(
    "trendspark_ingest_cycles_total",
    "Number of ingest cycles executed.",
)

ALERT_DELIVERY_TOTAL = Counter(
    "trendspark_alert_delivery_total",
    "Alert delivery attempts grouped by channel, category, and status.",
    labelnames=("channel", "category", "status"),
)

OPENAI_REQUESTS_TOTAL = Counter(
    "trendspark_openai_requests_total",
    "OpenAI requests issued by feature.",
    labelnames=("kind",),
)

OPENAI_TOKENS_TOTAL = Counter(
    "trendspark_openai_tokens_total",
    "Total OpenAI tokens consumed by feature.",
    labelnames=("kind",),
)

JOB_DURATION_SECONDS = Histogram(
    "trendspark_job_duration_seconds",
    "Duration of scheduled jobs in seconds.",
    labelnames=("job",),
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
)

JOB_RUNS_TOTAL = Counter(
    "trendspark_job_runs_total",
    "Scheduled job runs grouped by status.",
    labelnames=("job", "status"),
)

QUEUE_BACKLOG = Gauge(
    "trendspark_queue_backlog",
    "Backlog gauges for pending work (alerts, replies, etc.).",
    labelnames=("type",),
)


def record_ingest_counts(counts: Mapping[str, int]) -> None:
    """Increment ingest counters for each source and count the cycle."""
    INGEST_CYCLES_TOTAL.inc()
    for source, count in counts.items():
        if count:
            INGEST_ITEMS_TOTAL.labels(source=source or "unknown").inc(count)


def record_alert_delivery(channel: str, category: str | None, status: str) -> None:
    ALERT_DELIVERY_TOTAL.labels(
        channel=channel or "unknown",
        category=category or "unspecified",
        status=status,
    ).inc()


def record_openai_usage(kind: str, total_tokens: int | None = None) -> None:
    OPENAI_REQUESTS_TOTAL.labels(kind=kind).inc()
    if total_tokens is not None:
        try:
            tokens = max(int(total_tokens), 0)
        except (TypeError, ValueError):
            tokens = None
        if tokens:
            OPENAI_TOKENS_TOTAL.labels(kind=kind).inc(tokens)


def observe_job_duration(job: str, duration_seconds: float, status: str) -> None:
    JOB_DURATION_SECONDS.labels(job=job).observe(max(duration_seconds, 0.0))
    JOB_RUNS_TOTAL.labels(job=job, status=status).inc()


def set_queue_backlog(kind: str, value: int) -> None:
    QUEUE_BACKLOG.labels(type=kind).set(max(value, 0))


# Initialise known gauges to zero so they appear before work is processed.
QUEUE_BACKLOG.labels(type="alerts_pending").set(0)
QUEUE_BACKLOG.labels(type="replies_pending").set(0)
