from __future__ import annotations

import logging
import signal
import threading
import time
from typing import Any, Literal

from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .db import Base, engine
from .auth import ApiTokenMiddleware, SEED_TOKENS, require_roles, AuthenticatedUser
from .ingestion.stream import refresh_stream_rules, start_filtered_stream, stop_filtered_stream
from .scheduler import (
    JOB_HANDLERS,
    build_scheduler,
    create_scheduler_config,
    delete_scheduler_config,
    get_scheduler,
    list_scheduler_configs,
    run_job_now,
    scheduler_job_identifier,
    serialize_scheduler_config,
    toggle_job,
    update_scheduler_config,
)
from .logging import configure_logging, CorrelationIdMiddleware

configure_logging()
log = logging.getLogger(__name__)

app = FastAPI(title="Trend Spark Worker")
app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Request-ID",
    skip_paths={"/health"},
)
app.add_middleware(
    ApiTokenMiddleware,
    seed_tokens=SEED_TOKENS,
    exempt_path_prefixes={"/health", "/live"},
)
Instrumentator().instrument(app).expose(
    app,
    include_in_schema=False,
    endpoint="/metrics",
)

_shutdown = threading.Event()


class SchedulerRunRequest(BaseModel):
    config_id: int = Field(..., ge=1)


class SchedulerConfigBase(BaseModel):
    job_id: str
    name: str | None = None
    cron: str
    enabled: bool = True
    priority: int = Field(default=5, ge=1, le=100)
    concurrency_limit: int = Field(default=1, ge=1, le=20)
    lock_timeout_seconds: int = Field(default=300, ge=30, le=7200)
    parameters: dict[str, Any] | None = None
    growth_profile_id: int | None = Field(default=None, ge=1)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        if value not in JOB_HANDLERS:
            raise ValueError(f"Unknown job_id '{value}'. Valid options: {', '.join(sorted(JOB_HANDLERS))}")
        return value

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        try:
            CronTrigger.from_crontab(value)
        except ValueError as exc:  # pragma: no cover - validation path
            raise ValueError(f"Invalid cron expression: {exc}") from exc
        return value


class SchedulerConfigCreate(SchedulerConfigBase):
    pass


class SchedulerConfigUpdate(BaseModel):
    job_id: str | None = None
    name: str | None = None
    cron: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=100)
    concurrency_limit: int | None = Field(default=None, ge=1, le=20)
    lock_timeout_seconds: int | None = Field(default=None, ge=30, le=7200)
    parameters: dict[str, Any] | None = None
    growth_profile_id: int | None = Field(default=None, ge=1)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in JOB_HANDLERS:
            raise ValueError(f"Unknown job_id '{value}'. Valid options: {', '.join(sorted(JOB_HANDLERS))}")
        return value

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            CronTrigger.from_crontab(value)
        except ValueError as exc:  # pragma: no cover
            raise ValueError(f"Invalid cron expression: {exc}") from exc
        return value


class SchedulerToggleRequest(BaseModel):
    config_id: int = Field(..., ge=1)
    action: Literal["pause", "resume"]


def _serialize_config_payload(cfg_dict: dict) -> dict:
    scheduler = get_scheduler()
    job = None
    if scheduler:
        job = scheduler.get_job(scheduler_job_identifier(cfg_dict["config_id"]))
    payload = dict(cfg_dict)
    payload["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None
    payload["paused"] = not cfg_dict["enabled"]
    return payload


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)

    scheduler = build_scheduler()
    scheduler.start()
    log.info("Worker scheduler started")

    if settings.x_stream_enabled:
        start_filtered_stream()
        log.info("Filtered stream started")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: _shutdown.set())


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler = get_scheduler()
    if scheduler:
        scheduler.shutdown(wait=False)
    stop_filtered_stream()
    _shutdown.set()


@app.get("/health")
def health() -> dict:
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs() if scheduler else []
    return {
        "ok": scheduler is not None,
        "jobs": len(jobs),
        "stream_enabled": settings.x_stream_enabled,
    }


@app.get("/live")
def live() -> dict[str, bool]:
    return {"ok": True}


@app.get("/scheduler/jobs")
def scheduler_jobs(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> list[dict]:
    configs = list_scheduler_configs()
    return [_serialize_config_payload(serialize_scheduler_config(cfg)) for cfg in configs]


def _run_job_async(config_id: int) -> None:
    success = run_job_now(config_id)
    if not success:
        log.error("scheduler.run.failed", extra={"config_id": config_id})


@app.post("/scheduler/run", status_code=202)
def scheduler_run(
    req: SchedulerRunRequest,
    background: BackgroundTasks,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    background.add_task(_run_job_async, req.config_id)
    return {"queued": True, "config_id": req.config_id}


@app.post("/scheduler/toggle")
def scheduler_toggle(
    req: SchedulerToggleRequest,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    if not toggle_job(req.config_id, req.action):
        raise HTTPException(status_code=400, detail="Failed to toggle job")
    return {"ok": True}


@app.post("/scheduler/configs")
def scheduler_config_create(
    req: SchedulerConfigCreate,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    cfg = create_scheduler_config(**req.model_dump())
    return _serialize_config_payload(serialize_scheduler_config(cfg))


@app.put("/scheduler/configs/{config_id}")
def scheduler_config_update_endpoint(
    config_id: int,
    req: SchedulerConfigUpdate,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    payload = req.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No update fields provided")
    cfg = update_scheduler_config(config_id, **payload)
    if not cfg:
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    return _serialize_config_payload(serialize_scheduler_config(cfg))


@app.delete("/scheduler/configs/{config_id}")
def scheduler_config_delete(
    config_id: int,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    if not delete_scheduler_config(config_id):
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    return {"ok": True}


@app.post("/stream/refresh")
def stream_refresh(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> dict:
    refresh_stream_rules()
    return {"ok": True}


def run_worker() -> None:
    """Blocking loop so the worker can be launched without uvicorn."""
    Base.metadata.create_all(bind=engine)
    scheduler = build_scheduler()
    scheduler.start()
    if settings.x_stream_enabled:
        start_filtered_stream()
    try:
        while not _shutdown.is_set():
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)
        stop_filtered_stream()


__all__ = ["app", "run_worker"]
