from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Literal
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .db import session_scope
from .generator import craft_replies_for_post, ensure_today_ideas
from .growth import get_growth_state
from .ingestion.ingest import ingest_cycle
from .ingestion.x_client import fetch_trending_hashtags
from .logging import correlation_context
from .models import JobRun, Post, SchedulerConfig, SchedulerLock
from .notifier import send_telegram_message
from .metrics import observe_job_duration, set_queue_backlog
from .ranking import rank_and_mark, top_conversations
from .timeutils import as_utc_naive

log = logging.getLogger(__name__)

_SCHEDULER: BackgroundScheduler | None = None

JOB_FAILURE_THRESHOLD = 3
JOB_FAILURE_ALERT_COOLDOWN = timedelta(minutes=30)
_job_failure_counts: defaultdict[str, int] = defaultdict(int)
_job_failure_last_alert: dict[str, datetime] = {}

CONFIG_JOB_PREFIX = "cfg:"
JOB_HANDLERS: dict[str, Callable[..., None]] = {}


def _total_engagement(post: Post) -> int:
    return (post.like_count or 0) + (post.repost_count or 0) + (post.reply_count or 0)


def _notify_job_failure(job_id: str, detail: str | None = None) -> None:
    message = f"Job '{job_id}' has failed repeatedly."
    if detail:
        trimmed = detail.strip()
        if len(trimmed) > 400:
            trimmed = trimmed[:400] + "..."
        message += f"\nDetail: {trimmed}"
    send_telegram_message(message, category="job_alert")


def _track_job_result(job_id: str, status: str, detail: str | None = None) -> None:
    now = datetime.utcnow()
    if status == "error":
        _job_failure_counts[job_id] += 1
        if _job_failure_counts[job_id] >= JOB_FAILURE_THRESHOLD:
            last_alert = _job_failure_last_alert.get(job_id)
            if not last_alert or now - last_alert >= JOB_FAILURE_ALERT_COOLDOWN:
                _notify_job_failure(job_id, detail)
                _job_failure_last_alert[job_id] = now
    else:
        _job_failure_counts[job_id] = 0


def job_ingest_and_rank(
    *,
    max_x: int = 30,
    max_reddit_per_sub: int = 25,
    alert_recency_minutes: int | None = None,
    top_limit: int = 10,
    growth_profile_id: int | None = None,
) -> None:
    recency_minutes = alert_recency_minutes or settings.alert_recency_minutes
    growth_state = get_growth_state(growth_profile_id, allow_inactive=True)
    with correlation_context() as cid:
        started = time.perf_counter()
        alerts_sent = 0
        outcome = "ok"
        log.info(
            "job.start",
            extra={
                "job": "ingest_rank",
                "growth_profile_id": growth_state.id,
                "growth_profile_name": growth_state.name,
            },
        )
        try:
            ingest_cycle(
                max_x=max_x,
                max_reddit_per_sub=max_reddit_per_sub,
                keywords=growth_state.keywords,
            )
            try:
                trending_hashtags = fetch_trending_hashtags()
            except Exception as exc:
                log.warning("failed to load trending hashtags: %s", exc)
                trending_hashtags = []
            rank_and_mark(
                recent_minutes=recency_minutes,
                priority_keywords=growth_state.keywords,
                priority_watchlist=growth_state.watchlist,
                trending_hashtags=trending_hashtags,
            )

            now = datetime.utcnow()
            cutoff = now - timedelta(minutes=recency_minutes)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            posts = top_conversations(limit=top_limit, min_created_at=recent_cutoff)

            def _recent_posts():
                for post in posts:
                    created = as_utc_naive(post.created_at)
                    if created is None:
                        continue
                    if post.last_alerted_at:
                        continue
                    if created >= recent_cutoff:
                        yield post

            fallback_candidate = max(
                _recent_posts(),
                key=_total_engagement,
                default=None,
            )

            summary_lines: list[str] = []
            payload_posts: list[dict[str, Any]] = []

            with session_scope() as s:
                for post in posts:
                    if not post.trending:
                        continue
                    if post.last_alerted_at:
                        continue
                    ts = as_utc_naive(post.trending_since)
                    if ts is None:
                        continue
                    if ts < cutoff:
                        continue

                    last_alert_score = post.last_alerted_virality
                    if (
                        last_alert_score is not None
                        and abs(last_alert_score - post.virality_score) < 1e-3
                    ):
                        log.info(
                            "alert.skip_unchanged",
                            extra={
                                "platform": post.platform,
                                "post_id": post.post_id,
                                "virality": post.virality_score,
                            },
                        )
                        continue

                    suggestions = list(post.reply_suggestions or [])
                    if not suggestions:
                        generated = craft_replies_for_post(
                            post, settings.tone_priorities
                        )
                        suggestions = generated or []
                        if suggestions:
                            db_post = (
                                s.query(Post)
                                .filter(
                                    Post.platform == post.platform,
                                    Post.post_id == post.post_id,
                                )
                                .first()
                            )
                            if db_post:
                                db_post.reply_suggestions = suggestions
                                s.flush()

                    handle = (post.author or "").lstrip("@")
                    handle_display = f"X {post.virality_score:.2f}"
                    if handle:
                        handle_display = f"{handle_display} | {handle}"
                    preview = (post.url or post.text[:90]).strip()
                    summary_lines.append(f"• {handle_display}")
                    summary_lines.append(f"  {preview}")

                    display_suggestions = []
                    for suggestion in suggestions[:2]:
                        if isinstance(suggestion, dict):
                            tone = suggestion.get("tone")
                            reply_text = suggestion.get("reply")
                        else:
                            tone = None
                            reply_text = str(suggestion)
                        if not reply_text:
                            continue
                        display_suggestions.append({"tone": tone, "reply": reply_text})
                        tone_prefix = f"[{tone}] " if tone else ""
                        summary_lines.append(f"    - {tone_prefix}{reply_text}")

                    payload_posts.append(
                        {
                            "platform": post.platform,
                            "post_id": post.post_id,
                            "virality": post.virality_score,
                            "velocity": post.velocity_score,
                            "suggestions": display_suggestions,
                        }
                    )

                    db_post = (
                        s.query(Post)
                        .filter(
                            Post.platform == post.platform, Post.post_id == post.post_id
                        )
                        .first()
                    )
                    if db_post:
                        db_post.last_alerted_at = now
                        db_post.last_alerted_virality = post.virality_score

            payload: dict[str, Any]
            if payload_posts:
                alerts_sent = len(payload_posts)
                header = f"Engagement suggestions ({now.strftime('%H:%M')}):"
                payload = {"posts": payload_posts}
                send_telegram_message(
                    "\n".join([header, *summary_lines]),
                    category="trending_alert",
                    payload=payload,
                )
                outcome = "alerts_sent"
            elif fallback_candidate is not None:
                eng_total = _total_engagement(fallback_candidate)
                handle = (fallback_candidate.author or "").lstrip("@")
                display_name = (
                    f"@{handle}" if handle else fallback_candidate.author or "Unknown"
                )
                fallback_lines = [
                    f"Engagement suggestion ({now.strftime('%H:%M')}) – monitoring for traction.",
                    f"- {display_name}",
                    f"  {fallback_candidate.url or fallback_candidate.text[:90]}",
                    f"  {eng_total} engagements; watching for lift.",
                ]
                payload = {
                    "fallback": True,
                    "posts": [
                        {
                            "platform": fallback_candidate.platform,
                            "post_id": fallback_candidate.post_id,
                            "engagement_total": eng_total,
                            "fallback": True,
                        }
                    ],
                }
                send_telegram_message(
                    "\n".join(fallback_lines),
                    category="trending_alert",
                    payload=payload,
                )
                with session_scope() as s:
                    db_post = (
                        s.query(Post)
                        .filter(
                            Post.platform == fallback_candidate.platform,
                            Post.post_id == fallback_candidate.post_id,
                        )
                        .first()
                    )
                    if db_post:
                        db_post.last_alerted_at = now
                        db_post.last_alerted_virality = (
                            fallback_candidate.virality_score
                        )
                alerts_sent = 1
                summary_lines[:] = fallback_lines
                outcome = "fallback_alert"
            else:
                log.info("alert.no_new_trending", extra={"job": "ingest_rank"})
                outcome = "no_alerts"
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            with session_scope() as s:
                trending_posts = s.query(Post).filter(Post.trending.is_(True)).all()
            alerts_backlog = sum(
                1 for post in trending_posts if not post.last_alerted_at
            )
            replies_backlog = sum(
                1 for post in trending_posts if not (post.reply_suggestions or [])
            )
            set_queue_backlog("alerts_pending", alerts_backlog)
            set_queue_backlog("replies_pending", replies_backlog)
            observe_job_duration("ingest_rank", duration_ms / 1000.0, outcome)
            log.info(
                "job.complete",
                extra={
                    "job": "ingest_rank",
                    "duration_ms": duration_ms,
                    "alerts": alerts_sent,
                    "outcome": outcome,
                    "correlation_id": cid,
                    "growth_profile_id": growth_state.id,
                    "growth_profile_name": growth_state.name,
                },
            )


def job_generate_replies_for_trending(
    *, limit: int = 10, growth_profile_id: int | None = None
) -> None:
    with correlation_context() as cid:
        started = time.perf_counter()
        generated = 0
        log.info("job.start", extra={"job": "gen_replies"})
        try:
            with session_scope() as s:
                posts = (
                    s.query(Post)
                    .filter(Post.trending.is_(True))
                    .order_by(Post.virality_score.desc())
                    .limit(limit)
                    .all()
                )
                for post in posts:
                    if post.reply_suggestions:
                        continue
                    suggestions = craft_replies_for_post(post, settings.tone_priorities)
                    post.reply_suggestions = suggestions
                    if suggestions:
                        generated += 1
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            status = "generated" if generated else "noop"
            observe_job_duration("gen_replies", duration_ms / 1000.0, status)
            log.info(
                "job.complete",
                extra={
                    "job": "gen_replies",
                    "generated": generated,
                    "duration_ms": duration_ms,
                    "correlation_id": cid,
                },
            )


def job_daily_ideas(
    *, announce: bool = True, growth_profile_id: int | None = None
) -> None:
    with correlation_context() as cid:
        started = time.perf_counter()
        result = "no_ideas"
        ideas: list[str] = []
        log.info("job.start", extra={"job": "daily_ideas"})
        try:
            ideas = ensure_today_ideas(growth_profile_id)
            if ideas and announce:
                msg = "Today's 5 tweet ideas:\n- " + "\n- ".join(ideas)
                send_telegram_message(msg, category="daily_ideas")
                result = "sent"
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            observe_job_duration("daily_ideas", duration_ms / 1000.0, result)
            log.info(
                "job.complete",
                extra={
                    "job": "daily_ideas",
                    "duration_ms": duration_ms,
                    "ideas": len(ideas),
                    "outcome": result,
                    "correlation_id": cid,
                },
            )


JOB_HANDLERS = {
    "ingest_rank": job_ingest_and_rank,
    "gen_replies": job_generate_replies_for_trending,
    "daily_ideas": job_daily_ideas,
}


def _config_job_id(config_id: int) -> str:
    return f"{CONFIG_JOB_PREFIX}{config_id}"


def _ensure_default_configs() -> None:
    with session_scope() as s:
        existing = s.query(SchedulerConfig).count()
        if existing:
            return
        profile_id = get_growth_state().id
        defaults = [
            SchedulerConfig(
                job_id="ingest_rank",
                name="ingest + rank",
                cron="*/30 * * * *",
                growth_profile_id=profile_id,
                parameters={"max_x": 30},
            ),
            SchedulerConfig(
                job_id="gen_replies",
                name="generate trending replies",
                cron="*/15 * * * *",
                growth_profile_id=profile_id,
                parameters={"limit": 10},
            ),
            SchedulerConfig(
                job_id="daily_ideas",
                name="daily ideas",
                cron=f"0 {settings.ideas_time_hour} * * *",
                growth_profile_id=profile_id,
                parameters={"announce": True},
            ),
        ]
        for cfg in defaults:
            s.add(cfg)


def list_scheduler_configs() -> list[SchedulerConfig]:
    with session_scope() as s:
        configs = (
            s.query(SchedulerConfig)
            .order_by(SchedulerConfig.priority, SchedulerConfig.id)
            .all()
        )
        for cfg in configs:
            s.expunge(cfg)
        return configs


def _fetch_config(config_id: int) -> SchedulerConfig | None:
    with session_scope() as s:
        config = s.get(SchedulerConfig, config_id)
        if config:
            s.expunge(config)
        return config


def _cleanup_expired_locks(session, config_id: int) -> None:
    now = datetime.utcnow()
    session.query(SchedulerLock).filter(
        SchedulerLock.config_id == config_id,
        SchedulerLock.expires_at <= now,
    ).delete(synchronize_session=False)


def _acquire_scheduler_lock(config: SchedulerConfig) -> str | None:
    token = uuid4().hex
    now = datetime.utcnow()
    limit = max(1, config.concurrency_limit or 1)
    timeout = max(10, config.lock_timeout_seconds or 300)
    expires_at = now + timedelta(seconds=timeout)
    with session_scope() as s:
        _cleanup_expired_locks(s, config.id)
        active = (
            s.query(SchedulerLock)
            .filter(
                SchedulerLock.config_id == config.id,
                SchedulerLock.expires_at > now,
            )
            .count()
        )
        if active >= limit:
            return None
        lock = SchedulerLock(
            config_id=config.id,
            lock_token=token,
            acquired_at=now,
            expires_at=expires_at,
        )
        s.add(lock)
    return token


def _release_scheduler_lock(config_id: int, token: str) -> None:
    with session_scope() as s:
        s.query(SchedulerLock).filter(
            SchedulerLock.config_id == config_id,
            SchedulerLock.lock_token == token,
        ).delete(synchronize_session=False)


def _record_job_run(
    config: SchedulerConfig,
    *,
    status: str,
    detail: str | None,
    duration_ms: float | None,
    correlation_id: str | None,
) -> None:
    with session_scope() as s:
        s.add(
            JobRun(
                job_id=config.job_id,
                config_id=config.id,
                status=status,
                duration_ms=duration_ms,
                detail=detail,
                correlation_id=correlation_id,
            )
        )


def _execute_configured_job(config_id: int) -> None:
    config = _fetch_config(config_id)
    if not config or not config.enabled:
        return
    handler = JOB_HANDLERS.get(config.job_id)
    if not handler:
        log.error(
            "scheduler.unknown_job",
            extra={"job_id": config.job_id, "config_id": config.id},
        )
        return

    lock_token = _acquire_scheduler_lock(config)
    if not lock_token:
        log.info(
            "scheduler.lock_skipped",
            extra={"job_id": config.job_id, "config_id": config.id},
        )
        return

    with correlation_context() as cid:
        started = time.perf_counter()
        status = "success"
        detail = None
        try:
            params = dict(config.parameters or {})
            if config.growth_profile_id and "growth_profile_id" not in params:
                params["growth_profile_id"] = config.growth_profile_id
            handler(**params)
        except Exception as exc:  # pragma: no cover
            status = "error"
            detail = str(exc)
            log.exception(
                "scheduler.job_failed",
                extra={"job_id": config.job_id, "config_id": config.id},
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            _record_job_run(
                config,
                status=status,
                detail=detail,
                duration_ms=duration_ms,
                correlation_id=cid,
            )
            _track_job_result(config.job_id, status, detail)
            _release_scheduler_lock(config.id, lock_token)


def refresh_scheduler_jobs() -> None:
    scheduler = get_scheduler()
    if scheduler is None:
        return
    _ensure_default_configs()
    configs = list_scheduler_configs()
    existing_jobs = {job.id for job in scheduler.get_jobs()}
    desired_jobs: set[str] = set()

    for cfg in configs:
        job_identifier = _config_job_id(cfg.id)
        desired_jobs.add(job_identifier)
        if not cfg.enabled:
            if job_identifier in existing_jobs:
                scheduler.remove_job(job_identifier)
            continue
        try:
            trigger = CronTrigger.from_crontab(cfg.cron)
        except ValueError as exc:
            log.error(
                "scheduler.invalid_cron",
                extra={"config_id": cfg.id, "cron": cfg.cron, "error": str(exc)},
            )
            continue
        scheduler.add_job(
            _execute_configured_job,
            trigger,
            id=job_identifier,
            name=cfg.name or cfg.job_id,
            kwargs={"config_id": cfg.id},
            replace_existing=True,
            max_instances=max(1, cfg.concurrency_limit or 1),
        )

    for job_id in existing_jobs:
        if job_id.startswith(CONFIG_JOB_PREFIX) and job_id not in desired_jobs:
            scheduler.remove_job(job_id)


def build_scheduler() -> BackgroundScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = BackgroundScheduler()
    refresh_scheduler_jobs()
    return _SCHEDULER


def get_scheduler() -> BackgroundScheduler | None:
    return _SCHEDULER


def run_job_now(config_id: int) -> bool:
    try:
        _execute_configured_job(config_id)
        return True
    except Exception:
        return False


def toggle_job(config_id: int, action: Literal["pause", "resume"]) -> bool:
    with session_scope() as s:
        config = s.get(SchedulerConfig, config_id)
        if not config:
            return False
        config.enabled = action == "resume"
    refresh_scheduler_jobs()
    return True


def scheduler_job_identifier(config_id: int) -> str:
    return _config_job_id(config_id)


def create_scheduler_config(
    *,
    job_id: str,
    name: str | None,
    cron: str,
    enabled: bool = True,
    priority: int = 5,
    concurrency_limit: int = 1,
    lock_timeout_seconds: int = 300,
    parameters: dict[str, Any] | None = None,
    growth_profile_id: int | None = None,
) -> SchedulerConfig:
    if job_id not in JOB_HANDLERS:
        raise ValueError(
            f"Unknown job_id '{job_id}'. Valid jobs: {', '.join(sorted(JOB_HANDLERS))}"
        )
    profile = get_growth_state(growth_profile_id, allow_inactive=True)
    with session_scope() as s:
        cfg = SchedulerConfig(
            job_id=job_id,
            name=name,
            cron=cron,
            enabled=enabled,
            priority=priority,
            concurrency_limit=concurrency_limit,
            lock_timeout_seconds=lock_timeout_seconds,
            parameters=parameters,
            growth_profile_id=profile.id,
        )
        s.add(cfg)
        s.flush()
        s.refresh(cfg)
        s.expunge(cfg)
    refresh_scheduler_jobs()
    return cfg


def update_scheduler_config(config_id: int, **changes: Any) -> SchedulerConfig | None:
    editable_fields = {
        "job_id",
        "name",
        "cron",
        "enabled",
        "priority",
        "concurrency_limit",
        "lock_timeout_seconds",
        "parameters",
        "growth_profile_id",
    }
    payload = {k: v for k, v in changes.items() if k in editable_fields}
    if "job_id" in payload and payload["job_id"] not in JOB_HANDLERS:
        raise ValueError(f"Unknown job_id '{payload['job_id']}'.")
    if "growth_profile_id" in payload:
        profile = get_growth_state(payload["growth_profile_id"], allow_inactive=True)
        payload["growth_profile_id"] = profile.id
    with session_scope() as s:
        cfg = s.get(SchedulerConfig, config_id)
        if not cfg:
            return None
        for key, value in payload.items():
            setattr(cfg, key, value)
        s.flush()
        s.refresh(cfg)
        s.expunge(cfg)
    refresh_scheduler_jobs()
    return cfg


def delete_scheduler_config(config_id: int) -> bool:
    removed = False
    with session_scope() as s:
        cfg = s.get(SchedulerConfig, config_id)
        if cfg:
            s.delete(cfg)
            removed = True
    if removed:
        refresh_scheduler_jobs()
    return removed


def serialize_scheduler_config(cfg: SchedulerConfig) -> dict[str, Any]:
    profile_summary = None
    if cfg.growth_profile_id:
        try:
            profile = get_growth_state(cfg.growth_profile_id, allow_inactive=True)
            profile_summary = {
                "id": profile.id,
                "name": profile.name,
                "is_default": profile.is_default,
                "is_active": profile.is_active,
            }
        except ValueError:
            profile_summary = None
    return {
        "config_id": cfg.id,
        "job_id": cfg.job_id,
        "name": cfg.name,
        "cron": cfg.cron,
        "enabled": cfg.enabled,
        "priority": cfg.priority,
        "concurrency_limit": cfg.concurrency_limit,
        "lock_timeout_seconds": cfg.lock_timeout_seconds,
        "parameters": cfg.parameters or {},
        "created_at": cfg.created_at.isoformat(),
        "updated_at": cfg.updated_at.isoformat(),
        "growth_profile_id": cfg.growth_profile_id,
        "growth_profile": profile_summary,
    }


__all__ = [
    "JOB_HANDLERS",
    "build_scheduler",
    "get_scheduler",
    "create_scheduler_config",
    "update_scheduler_config",
    "delete_scheduler_config",
    "list_scheduler_configs",
    "refresh_scheduler_jobs",
    "scheduler_job_identifier",
    "serialize_scheduler_config",
    "job_daily_ideas",
    "job_generate_replies_for_trending",
    "job_ingest_and_rank",
    "run_job_now",
    "toggle_job",
]
