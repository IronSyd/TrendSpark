from __future__ import annotations

import logging
import re
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Annotated, Literal, Any

import httpx
from sqlalchemy import func, text

from fastapi import FastAPI, Body, HTTPException, Depends, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .config import settings
from .logging import (
    CorrelationIdMiddleware,
    configure_logging,
    inject_correlation_header,
)
from .db import session_scope
from .models import Post, BrandProfile, Notification, StreamRule, IngestAudit
from .ranking import top_conversations
from .generator import ensure_today_ideas
from .growth import (
    get_growth_state,
    update_growth_state,
    list_growth_profiles,
    create_growth_profile,
    update_growth_profile,
    set_default_growth_profile,
    deactivate_growth_profile,
)
from .auth import (
    ApiTokenMiddleware,
    SERVICE_TOKEN,
    SEED_TOKENS,
    require_roles,
    AuthenticatedUser,
)
from .validation import (
    sanitize_text,
    sanitize_string_list,
    sanitize_identifier,
    sanitize_handles,
)
from .notifier import send_telegram_message

KEYWORD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$")
TONE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
POST_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9:_-]{1,64}$")
PLATFORM_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
JOB_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

configure_logging()
log = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=settings.api_rate_limits,
    headers_enabled=True,
)

_API_ERROR_WINDOW_SECONDS = 300
_API_ERROR_THRESHOLD = 5
_API_ERROR_ALERT_COOLDOWN = timedelta(minutes=30)
_api_error_events: deque[tuple[datetime, str, int]] = deque()
_last_api_error_alert: datetime | None = None


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


def _worker_request(method: str, path: str, payload: dict | None = None):
    base_url = str(settings.scheduler_url).rstrip("/")
    url = f"{base_url}{path}"
    headers: dict[str, str] = {}
    if SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {SERVICE_TOKEN}"
    http_headers = inject_correlation_header(headers) or None
    try:
        response = httpx.request(
            method, url, json=payload, headers=http_headers, timeout=10.0
        )
        response.raise_for_status()
    except httpx.RequestError as exc:
        log.error(
            "worker.request_failed",
            extra={"method": method, "url": url},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=503, detail="Worker service unavailable"
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or exc.response.reason_phrase
        log.error(
            "worker.request_error",
            extra={
                "method": method,
                "url": url,
                "status": exc.response.status_code,
                "detail": detail,
            },
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail=detail
        ) from exc

    if (
        response.headers.get("content-type", "").startswith("application/json")
        and response.text
    ):
        return response.json()
    if response.text:
        return response.text
    return None


def _track_api_error(path: str, status_code: int) -> None:
    if status_code < 500:
        return
    now = datetime.utcnow()
    _api_error_events.append((now, path, status_code))
    while (
        _api_error_events
        and (now - _api_error_events[0][0]).total_seconds() > _API_ERROR_WINDOW_SECONDS
    ):
        _api_error_events.popleft()
    if len(_api_error_events) < _API_ERROR_THRESHOLD:
        return
    global _last_api_error_alert
    if (
        _last_api_error_alert
        and now - _last_api_error_alert < _API_ERROR_ALERT_COOLDOWN
    ):
        return
    recent = list(_api_error_events)[-3:]
    recent_summary = ", ".join(f"{p} ({s})" for _, p, s in recent)
    message = (
        f"⚠️ API errors spiking: {len(_api_error_events)} responses ≥500 in the last "
        f"{_API_ERROR_WINDOW_SECONDS // 60} minutes.\nRecent endpoints: {recent_summary or 'n/a'}"
    )
    if send_telegram_message(message, category="api_alert"):
        _last_api_error_alert = now


app = FastAPI(title="Trend Spark AI")
app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Request-ID",
    skip_paths={"/health"},
)
app.add_middleware(
    ApiTokenMiddleware,
    seed_tokens=SEED_TOKENS,
    exempt_path_prefixes={"/health", "/live", "/docs", "/openapi.json", "/redoc"},
)
cors_allow_origins = [
    str(origin).rstrip("/") for origin in settings.cors_allow_origins
] or ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
Instrumentator().instrument(app).expose(
    app,
    include_in_schema=False,
    endpoint="/metrics",
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    _track_api_error(request.url.path, response.status_code)
    log.info(
        "request.completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/live")
def live() -> dict[str, bool]:
    return {"ok": True}


def _check_database() -> tuple[bool, str | None]:
    try:
        with session_scope() as s:
            s.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - diagnostics
        return False, str(exc)


def _check_worker() -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        result = _worker_request("GET", "/health", None)
        if isinstance(result, dict):
            return bool(result.get("ok")), result, None
        return True, {"detail": result}, None
    except HTTPException as exc:
        return False, None, str(exc.detail)
    except Exception as exc:  # pragma: no cover - diagnostics
        return False, None, str(exc)


def _check_telegram() -> tuple[bool, str | None]:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing"
    try:
        headers = inject_correlation_header({})
        response = httpx.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe",
            headers=headers,
            timeout=5.0,
        )
        data = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if response.status_code == 200 and data.get("ok"):
            username = data.get("result", {}).get("username")
            return True, f"bot:{username}" if username else None
        detail = data.get("description") if isinstance(data, dict) else response.text
        return False, detail or f"HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - diagnostics
        return False, str(exc)


@app.get("/health")
def health():
    growth = get_growth_state()
    db_ok, db_detail = _check_database()
    worker_ok, worker_info, worker_detail = _check_worker()
    telegram_ok, telegram_detail = _check_telegram()
    overall_ok = db_ok and worker_ok and telegram_ok

    return {
        "ok": overall_ok,
        "services": {
            "database": {"ok": db_ok, "detail": db_detail},
            "worker": {
                "ok": worker_ok,
                "detail": worker_detail,
                "info": worker_info if worker_info else None,
            },
            "telegram": {"ok": telegram_ok, "detail": telegram_detail},
        },
        "stream_enabled": settings.x_stream_enabled,
        "keywords": growth.keywords,
        "niche": growth.niche,
        "watchlist": growth.watchlist,
        "growth_profile": {
            "id": growth.id,
            "name": growth.name,
            "is_default": growth.is_default,
            "is_active": growth.is_active,
            "keywords": growth.keywords,
            "niche": growth.niche,
            "watchlist": growth.watchlist,
        },
    }


class BrandProfileIn(BaseModel):
    adjectives: list[str] | None = None
    voice_notes: str | None = None
    examples: list[str] | None = None

    @field_validator("adjectives", mode="before")
    @classmethod
    def validate_adjectives(cls, value):
        return sanitize_string_list(
            value,
            max_items=8,
            max_length=48,
            pattern=KEYWORD_RE,
            lower=False,
        )

    @field_validator("examples", mode="before")
    @classmethod
    def validate_examples(cls, value):
        return sanitize_string_list(
            value,
            max_items=5,
            max_length=280,
        )

    @field_validator("voice_notes")
    @classmethod
    def validate_voice_notes(cls, value):
        return sanitize_text(value, max_length=2000)


class NotificationOut(BaseModel):
    id: int
    created_at: str
    channel: str
    category: str | None
    message: str


class StreamRuleIn(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, value):
        cleaned = sanitize_text(value, max_length=512)
        if not cleaned:
            raise ValueError("rule value cannot be empty")
        return cleaned


class StreamRuleOut(BaseModel):
    id: int
    value: str
    created_at: str


class IngestAuditOut(BaseModel):
    id: int
    cycle_id: str
    source: str
    platform: str
    post_id: str | None
    author: str | None
    fetched_at: str
    item_created_at: str | None
    summary: str | None


class SchedulerToggleIn(BaseModel):
    job_id: str
    action: Literal["pause", "resume"]

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value):
        return sanitize_identifier(value, pattern=JOB_IDENTIFIER_RE, max_length=64)


class SchedulerRunIn(BaseModel):
    job_id: str

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value):
        return sanitize_identifier(value, pattern=JOB_IDENTIFIER_RE, max_length=64)


class GrowthUpdateIn(BaseModel):
    niche: str | None = None
    keywords: list[str]
    watchlist: list[str]

    @field_validator("niche")
    @classmethod
    def validate_niche(cls, value):
        return sanitize_text(value, max_length=128)

    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, value):
        return sanitize_string_list(
            value,
            max_items=24,
            max_length=48,
            pattern=KEYWORD_RE,
            lower=True,
        )

    @field_validator("watchlist", mode="before")
    @classmethod
    def validate_watchlist(cls, value):
        return sanitize_handles(value, max_items=24, max_length=32)


class GrowthOut(BaseModel):
    niche: str | None
    keywords: list[str]
    watchlist: list[str]


class GrowthProfileCreateIn(GrowthUpdateIn):
    name: str
    make_default: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_length=128)
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned


class GrowthProfileUpdateIn(BaseModel):
    name: str | None = None
    niche: str | None = None
    keywords: list[str] | None = None
    watchlist: list[str] | None = None
    is_active: bool | None = None
    make_default: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = sanitize_text(value, max_length=128)
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned

    @field_validator("niche")
    @classmethod
    def validate_niche(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_text(value, max_length=128)

    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, value):
        if value is None:
            return value
        return sanitize_string_list(
            value,
            max_items=24,
            max_length=48,
            pattern=KEYWORD_RE,
            lower=True,
        )

    @field_validator("watchlist", mode="before")
    @classmethod
    def validate_watchlist(cls, value):
        if value is None:
            return value
        return sanitize_handles(value, max_items=24, max_length=32)


class GrowthProfileOut(BaseModel):
    id: int
    name: str
    niche: str | None
    keywords: list[str]
    watchlist: list[str]
    is_default: bool
    is_active: bool
    created_at: str
    updated_at: str


def _growth_state_to_profile_out(state) -> dict:
    return GrowthProfileOut(
        id=state.id,
        name=state.name,
        niche=state.niche,
        keywords=state.keywords,
        watchlist=state.watchlist,
        is_default=state.is_default,
        is_active=state.is_active,
        created_at=state.created_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
    ).model_dump()


@limiter.limit("30/minute")
@app.get("/growth/settings")
def get_growth_settings_endpoint(
    request: Request,
    profile_id: Annotated[int | None, Query(ge=1)] = None,
):
    try:
        state = get_growth_state(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GrowthOut(
        niche=state.niche, keywords=state.keywords, watchlist=state.watchlist
    ).model_dump()


@limiter.limit("10/minute")
@app.post("/growth/settings")
def update_growth_settings_endpoint(
    request: Request,
    payload: GrowthUpdateIn,
    _: AuthenticatedUser = Depends(require_roles("admin")),
    profile_id: Annotated[int | None, Query(ge=1)] = None,
):
    state = update_growth_state(
        niche=payload.niche,
        keywords=payload.keywords,
        watchlist=payload.watchlist,
        profile_id=profile_id,
    )
    return GrowthOut(
        niche=state.niche, keywords=state.keywords, watchlist=state.watchlist
    ).model_dump()


@limiter.limit("30/minute")
@app.get("/growth/profiles")
def list_growth_profiles_endpoint(
    request: Request,
    include_inactive: Annotated[bool, Query()] = False,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    profiles = list_growth_profiles(include_inactive=include_inactive)
    return [_growth_state_to_profile_out(state) for state in profiles]


@limiter.limit("10/minute")
@app.post("/growth/profiles")
def create_growth_profile_endpoint(
    request: Request,
    payload: GrowthProfileCreateIn,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    state = create_growth_profile(
        name=payload.name,
        niche=payload.niche,
        keywords=payload.keywords,
        watchlist=payload.watchlist,
        make_default=payload.make_default,
    )
    return _growth_state_to_profile_out(state)


@limiter.limit("10/minute")
@app.put("/growth/profiles/{profile_id}")
def update_growth_profile_endpoint(
    request: Request,
    profile_id: Annotated[int, Path(ge=1)],
    payload: GrowthProfileUpdateIn,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    try:
        state = update_growth_profile(
            profile_id,
            name=payload.name,
            niche=payload.niche,
            keywords=payload.keywords,
            watchlist=payload.watchlist,
            is_active=payload.is_active,
            make_default=payload.make_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _growth_state_to_profile_out(state)


@limiter.limit("10/minute")
@app.post("/growth/profiles/{profile_id}/default")
def set_default_growth_profile_endpoint(
    request: Request,
    profile_id: Annotated[int, Path(ge=1)],
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    try:
        state = set_default_growth_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _growth_state_to_profile_out(state)


@limiter.limit("10/minute")
@app.delete("/growth/profiles/{profile_id}")
def deactivate_growth_profile_endpoint(
    request: Request,
    profile_id: Annotated[int, Path(ge=1)],
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    try:
        state = deactivate_growth_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _growth_state_to_profile_out(state)


class FunnelPoint(BaseModel):
    day: str
    impressions: int
    replies: int
    generated_replies_used: int
    logged_engagements: int


class ToneProfitabilityPoint(BaseModel):
    tone: str
    avg_engagement: float
    usage_count: int


class PlatformHistogramPoint(BaseModel):
    bucket: float
    count: int


class PlatformHistogram(BaseModel):
    platform: str
    virality: list[PlatformHistogramPoint]
    velocity: list[PlatformHistogramPoint]


class AlertImpactPost(BaseModel):
    platform: str
    post_id: str
    virality_at_alert: float | None
    velocity_at_alert: float | None
    current_virality: float | None
    current_velocity: float | None
    like_count: int | None
    reply_count: int | None
    repost_count: int | None
    view_count: int | None


class AlertImpactEngagement(BaseModel):
    total: int
    by_type: dict[str, int]


class AlertImpactItem(BaseModel):
    id: int
    created_at: str
    message: str
    posts: list[AlertImpactPost]
    engagements: AlertImpactEngagement


class AlertImpactTimelinePoint(BaseModel):
    timestamp: str
    engagements: int


class AlertImpactResponse(BaseModel):
    alerts: list[AlertImpactItem]
    timeline: list[AlertImpactTimelinePoint]
    window_minutes: int
    bucket_minutes: int


class WatchlistEntry(BaseModel):
    handle: str
    total_posts: int
    trending_posts: int
    captured_engagements: int
    last_seen: str | None
    recent_posts: list[dict]


class WatchlistAnalytics(BaseModel):
    entries: list[WatchlistEntry]
    days: int


@limiter.limit("60/minute")
@app.get("/conversations/top")
def conversations_top(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    cutoff = datetime.utcnow() - timedelta(hours=24)
    rows = top_conversations(limit=limit, min_created_at=cutoff)
    return [
        {
            "platform": r.platform,
            "post_id": r.post_id,
            "url": r.url,
            "text": r.text,
            "virality": r.virality_score,
            "velocity": r.velocity_score,
            "trending": r.trending,
            "replies": r.reply_suggestions or [],
        }
        for r in rows
    ]


@limiter.limit("5/minute")
@app.delete("/conversations")
def conversations_clear(
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    with session_scope() as s:
        deleted = s.query(Post).delete()
    return {"ok": True, "deleted": deleted}


@limiter.limit("60/minute")
@app.get("/conversations/{platform}/{post_id}")
def conversation_detail(
    request: Request,
    platform: str,
    post_id: str,
):
    platform = sanitize_identifier(
        platform, pattern=PLATFORM_IDENTIFIER_RE, max_length=16
    )
    post_id = sanitize_identifier(post_id, pattern=POST_IDENTIFIER_RE, max_length=64)
    with session_scope() as s:
        post = (
            s.query(Post)
            .filter(Post.platform == platform, Post.post_id == post_id)
            .first()
        )
        if not post:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {
            "platform": post.platform,
            "post_id": post.post_id,
            "author": post.author,
            "text": post.text,
            "url": post.url,
            "created_at": post.created_at.isoformat(),
            "metrics": {
                "likes": post.like_count,
                "replies": post.reply_count,
                "reposts": post.repost_count,
                "quotes": post.quote_count,
                "views": post.view_count,
            },
            "virality": post.virality_score,
            "velocity": post.velocity_score,
            "trending": post.trending,
            "replies": post.reply_suggestions or [],
            "tones": post.tones or [],
        }


@limiter.limit("30/minute")
@app.get("/ideas/today")
def ideas_today(request: Request):
    profile_raw = request.query_params.get("profile_id")
    profile_id = None
    if profile_raw:
        try:
            profile_id = int(profile_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="profile_id must be an integer")
    return ensure_today_ideas(profile_id)


@limiter.limit("10/minute")
@app.post("/brand/profile")
def update_brand_profile(
    request: Request,
    payload: BrandProfileIn = Body(...),
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    with session_scope() as s:
        row = s.query(BrandProfile).first()
        if not row:
            row = BrandProfile()
            s.add(row)
        row.adjectives = payload.adjectives
        row.voice_notes = payload.voice_notes
        row.examples = payload.examples
    return {"ok": True}


@limiter.limit("60/minute")
@app.get("/brand/profile")
def get_brand_profile(request: Request):
    with session_scope() as s:
        row = s.query(BrandProfile).first()
        if not row:
            return {
                "adjectives": [],
                "voice_notes": "",
                "examples": [],
            }
        return {
            "adjectives": row.adjectives or [],
            "voice_notes": row.voice_notes or "",
            "examples": row.examples or [],
        }


@limiter.limit("30/minute")
@app.get("/alerts/recent")
def alerts_recent(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
):
    with session_scope() as s:
        rows = [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "channel": row.channel,
                "category": row.category,
                "message": row.message,
            }
            for row in (
                s.query(Notification)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .all()
            )
        ]
    return [NotificationOut(**row).model_dump() for row in rows]


@limiter.limit("30/minute")
@app.get("/stream/rules")
def list_stream_rules(request: Request):
    with session_scope() as s:
        rows = s.query(StreamRule).order_by(StreamRule.created_at.asc()).all()
    return [
        StreamRuleOut(
            id=row.id, value=row.value, created_at=row.created_at.isoformat()
        ).model_dump()
        for row in rows
    ]


@limiter.limit("10/minute")
@app.post("/stream/rules")
def add_stream_rule(
    request: Request,
    payload: StreamRuleIn,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    value = payload.value

    with session_scope() as s:
        existing = s.query(StreamRule).filter(StreamRule.value == value).first()
        if existing:
            raise HTTPException(status_code=409, detail="Rule already exists")
        rule = StreamRule(value=value)
        s.add(rule)

    _worker_request("POST", "/stream/refresh")
    return {"ok": True}


@limiter.limit("30/minute")
@app.get("/ingest/audit")
def ingest_audit(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    source: Annotated[str | None, Query(max_length=16)] = None,
    cycle_id: Annotated[str | None, Query(max_length=32)] = None,
):
    with session_scope() as s:
        query = s.query(IngestAudit).order_by(IngestAudit.id.desc())
        if source:
            query = query.filter(IngestAudit.source == source)
        if cycle_id:
            query = query.filter(IngestAudit.cycle_id == cycle_id)
        rows = query.limit(limit).all()
    return [
        IngestAuditOut(
            id=row.id,
            cycle_id=row.cycle_id,
            source=row.source,
            platform=row.platform,
            post_id=row.post_id,
            author=row.author,
            fetched_at=row.fetched_at.isoformat(),
            item_created_at=(
                row.item_created_at.isoformat() if row.item_created_at else None
            ),
            summary=row.summary,
        ).model_dump()
        for row in rows
    ]


@limiter.limit("30/minute")
@app.get("/scheduler/jobs")
def scheduler_jobs(
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    return _worker_request("GET", "/scheduler/jobs", None)


@limiter.limit("10/minute")
@app.post("/scheduler/run")
async def scheduler_run(
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    payload = await request.json()
    return _worker_request("POST", "/scheduler/run", payload)


@limiter.limit("10/minute")
@app.post("/scheduler/toggle")
async def scheduler_toggle(
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    payload = await request.json()
    return _worker_request("POST", "/scheduler/toggle", payload)


@limiter.limit("10/minute")
@app.post("/scheduler/configs")
async def scheduler_config_create(
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    payload = await request.json()
    return _worker_request("POST", "/scheduler/configs", payload)


@limiter.limit("10/minute")
@app.put("/scheduler/configs/{config_id}")
async def scheduler_config_update(
    config_id: Annotated[int, Path(ge=1)],
    request: Request,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    payload = await request.json()
    return _worker_request("PUT", f"/scheduler/configs/{config_id}", payload)


@limiter.limit("10/minute")
@app.delete("/scheduler/configs/{config_id}")
def scheduler_config_delete(
    request: Request,
    config_id: Annotated[int, Path(ge=1)],
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    return _worker_request("DELETE", f"/scheduler/configs/{config_id}", None)


@limiter.limit("30/minute")
@app.get("/analytics/watchlist")
def watchlist_analytics(
    request: Request,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    state = get_growth_state()
    handles: list[tuple[str, str]] = []
    for raw in state.watchlist:
        cleaned = raw.strip()
        if not cleaned:
            continue
        normalized = cleaned.lstrip("@").lower()
        if not normalized:
            continue
        handles.append((cleaned, normalized))

    if not handles:
        return WatchlistAnalytics(entries=[], days=days).model_dump()

    cutoff = datetime.utcnow() - timedelta(days=days)
    entries: list[dict] = []

    with session_scope() as s:
        for display, normalized in handles:
            posts = (
                s.query(Post)
                .filter(func.lower(Post.author) == normalized)
                .filter(Post.created_at >= cutoff)
                .order_by(Post.created_at.desc())
                .all()
            )
            if not posts:
                entries.append(
                    WatchlistEntry(
                        handle=display,
                        total_posts=0,
                        trending_posts=0,
                        captured_engagements=0,
                        last_seen=None,
                        recent_posts=[],
                    ).model_dump()
                )
                continue

            total_posts = len(posts)
            trending_posts = sum(1 for post in posts if post.trending)
            captured_engagements = sum(
                int(post.like_count or 0)
                + int(post.reply_count or 0)
                + int(post.repost_count or 0)
                + int(post.quote_count or 0)
                for post in posts
            )
            last_seen = posts[0].created_at.isoformat()
            recent_posts = [
                {
                    "created_at": post.created_at.isoformat(),
                    "virality": post.virality_score,
                    "velocity": post.velocity_score,
                    "url": post.url,
                    "trending": bool(post.trending),
                }
                for post in posts[:5]
            ]

            entries.append(
                WatchlistEntry(
                    handle=display,
                    total_posts=total_posts,
                    trending_posts=trending_posts,
                    captured_engagements=captured_engagements,
                    last_seen=last_seen,
                    recent_posts=recent_posts,
                ).model_dump()
            )

    # Sort entries by recent activity to surface active watchlist handles first.
    entries.sort(key=lambda entry: entry["last_seen"] or "", reverse=True)
    return WatchlistAnalytics(entries=entries, days=days).model_dump()
