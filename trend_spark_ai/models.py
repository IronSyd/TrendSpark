from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    Index,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), index=True)
    post_id: Mapped[str] = mapped_column(String(64), index=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    like_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    repost_count: Mapped[int] = mapped_column(Integer, default=0)
    quote_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    last_alerted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_alerted_virality: Mapped[float | None] = mapped_column(Float, nullable=True)
    trending_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    trending_candidate_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    virality_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    velocity_score: Mapped[float] = mapped_column(Float, default=0.0)
    trending: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reply_suggestions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    prev_repost_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_metrics_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_platform_postid", "platform", "post_id", unique=True),
    )


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_day: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    ideas: Mapped[list] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BrandProfile(Base):
    __tablename__ = "brand_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjectives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    voice_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    channel: Mapped[str] = mapped_column(String(32))  # e.g. telegram
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StreamRule(Base):
    __tablename__ = "stream_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    value: Mapped[str] = mapped_column(String(512), unique=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    config_id: Mapped[int | None] = mapped_column(ForeignKey("scheduler_configs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16))  # success|error
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SchedulerConfig(Base):
    __tablename__ = "scheduler_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    growth_profile_id: Mapped[int | None] = mapped_column(ForeignKey("growth_config.id"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cron: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=1)
    lock_timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("job_id", "name", name="uq_scheduler_config_name_per_job"),
        Index("ix_scheduler_enabled_priority", "enabled", "priority"),
        Index("ix_scheduler_growth_profile", "growth_profile_id"),
    )


class SchedulerLock(Base):
    __tablename__ = "scheduler_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("scheduler_configs.id", ondelete="CASCADE"), index=True)
    lock_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    __table_args__ = (
        Index("ix_scheduler_locks_active", "config_id", "expires_at"),
    )


class GrowthConfig(Base):
    __tablename__ = "growth_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    name: Mapped[str] = mapped_column(String(128), default="Default profile", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    niche: Mapped[str | None] = mapped_column(String(128), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    watchlist: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_growth_config_default_flag", "is_default"),
        Index("ix_growth_config_active_flag", "is_active"),
    )


class IngestionState(Base):
    __tablename__ = "ingestion_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IngestAudit(Base):
    __tablename__ = "ingest_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(16), index=True)
    platform: Mapped[str] = mapped_column(String(16), index=True)
    post_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    item_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(
        "User", secondary="user_roles", back_populates="roles"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="user_roles", back_populates="users"
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
