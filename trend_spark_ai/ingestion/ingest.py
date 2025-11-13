from __future__ import annotations
from datetime import datetime, timezone
from typing import Sequence
import logging
import uuid

from sqlalchemy import select

from ..db import session_scope
from ..metrics import record_ingest_counts
from ..models import Post, IngestAudit
from .x_client import search_recent_tweets
from .reddit_client import fetch_reddit_trending

log = logging.getLogger(__name__)


def _normalize_datetime(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    # attempt to parse string formats if necessary
    try:
        parsed = datetime.fromisoformat(str(value))
    except Exception:
        return datetime.utcnow()
    if parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def upsert_post(session, data: dict) -> Post:
    existing = session.execute(
        select(Post).where(
            Post.platform == data["platform"], Post.post_id == data["post_id"]
        )
    ).scalar_one_or_none()

    if existing:
        # Update metrics and fields if changed
        metric_fields = [
            "like_count",
            "reply_count",
            "repost_count",
            "quote_count",
            "view_count",
        ]
        for f in ["text", "url"]:
            value = data.get(f)
            if value is not None:
                setattr(existing, f, value)
        for f in metric_fields:
            incoming = data.get(f)
            if incoming is None:
                continue
            setattr(existing, f, int(incoming))

        author_raw = data.get("author")
        if author_raw is not None:
            cleaned_author = str(author_raw).lstrip("@")
            if cleaned_author:
                existing.author = cleaned_author
        created_raw = data.get("created_at")
        if created_raw is not None:
            existing.created_at = _normalize_datetime(created_raw)
        existing.collected_at = datetime.utcnow()
        return existing

    author_raw = data.get("author")
    author_value: str | None
    if author_raw is None:
        author_value = None
    else:
        author_value = str(author_raw).lstrip("@")
        if not author_value:
            author_value = None

    post = Post(
        platform=data["platform"],
        post_id=data["post_id"],
        author=author_value,
        url=data.get("url"),
        text=data.get("text", ""),
        created_at=_normalize_datetime(data.get("created_at")),
        like_count=int(data.get("like_count", 0)),
        reply_count=int(data.get("reply_count", 0)),
        repost_count=int(data.get("repost_count", 0)),
        quote_count=int(data.get("quote_count", 0)),
        view_count=int(data.get("view_count", 0)),
        collected_at=datetime.utcnow(),
    )
    session.add(post)
    session.flush()
    return post


def ingest_cycle(
    max_x: int = 10,
    max_reddit_per_sub: int = 25,
    keywords: Sequence[str] | None = None,
) -> int:
    """One ingestion cycle across X and Reddit. Returns count upserted."""
    selected_keywords = [k for k in (keywords or []) if k]
    if not selected_keywords:
        log.warning("ingest.no_keywords", extra={"source": "growth"})
    keywords_for_sources = selected_keywords or []
    cycle_id = uuid.uuid4().hex
    total = 0
    counts: dict[str, int] = {"x": 0, "reddit": 0}
    with session_scope() as s:
        for item in search_recent_tweets(keywords_for_sources, max_results=max_x):
            post = upsert_post(s, item)
            total += 1
            counts["x"] += 1
            summary = (item.get("text") or post.text or "")[:280]
            s.add(
                IngestAudit(
                    cycle_id=cycle_id,
                    source="x",
                    platform=item.get("platform", "x"),
                    post_id=item.get("post_id"),
                    author=post.author,
                    item_created_at=(
                        _normalize_datetime(item.get("created_at"))
                        if item.get("created_at")
                        else post.created_at
                    ),
                    summary=summary,
                )
            )
        for item in fetch_reddit_trending(
            keywords_for_sources, limit_per_sub=max_reddit_per_sub
        ):
            post = upsert_post(s, item)
            total += 1
            counts["reddit"] += 1
            summary = (item.get("text") or post.text or "")[:280]
            s.add(
                IngestAudit(
                    cycle_id=cycle_id,
                    source="reddit",
                    platform=item.get("platform", "reddit"),
                    post_id=item.get("post_id"),
                    author=post.author,
                    item_created_at=(
                        _normalize_datetime(item.get("created_at"))
                        if item.get("created_at")
                        else post.created_at
                    ),
                    summary=summary,
                )
            )
    log.info("Ingested/upserted %d items", total)
    record_ingest_counts(counts)
    return total
