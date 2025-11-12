from __future__ import annotations
from datetime import datetime, timezone, timedelta
from math import log1p
from typing import Sequence
from sqlalchemy import select
from .db import session_scope
from .models import Post
from .timeutils import as_utc_naive
from .config import settings


def _time_decay(created_at: datetime) -> float:
    # Decay newer content less; older content more. 0..1
    if created_at.tzinfo is None or created_at.tzinfo.utcoffset(created_at) is None:
        created = created_at.replace(tzinfo=timezone.utc)
    else:
        created = created_at.astimezone(timezone.utc)
    age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600.0
    # 0h -> ~1.0, 24h -> ~0.5, 72h -> ~0.25
    return 1.0 / (1.0 + (age_hours / 24.0))


def compute_scores_for_post(p: Post) -> tuple[float, float]:
    # Velocity based on log metrics and time decay
    base = (
        0.5 * log1p(p.like_count)
        + 0.8 * log1p(p.repost_count + p.quote_count)
        + 0.7 * log1p(p.reply_count)
        + 0.3 * log1p(p.view_count)
    )
    decay = _time_decay(p.created_at)
    velocity = base * decay
    # Virality: emphasize network effects (reposts/quotes) and replies
    virality = (
        0.4 * log1p(p.like_count)
        + 1.0 * log1p(p.repost_count + p.quote_count)
        + 0.9 * log1p(p.reply_count)
        + 0.2 * log1p(p.view_count)
    )
    # Normalize to 0..1 soft range by dividing by a cap (empirical)
    v_cap = 10.0
    velocity_n = min(1.0, velocity / v_cap)
    virality_n = min(1.0, virality / v_cap)
    return virality_n, velocity_n


def _build_author_engagement_stats(posts: list[Post]) -> tuple[dict[str, float], float]:
    author_totals: dict[str, list[int]] = {}
    global_total = 0
    global_count = 0
    for p in posts:
        engagement = (p.like_count or 0) + (p.repost_count or 0) + (p.reply_count or 0)
        global_total += engagement
        global_count += 1
        if p.author:
            bucket = author_totals.setdefault(p.author, [0, 0])
            bucket[0] += engagement
            bucket[1] += 1
    author_avgs = {
        author: totals / count
        for author, (totals, count) in author_totals.items()
        if count > 0
    }
    global_avg = (global_total / global_count) if global_count else 0.0
    return author_avgs, global_avg


def _required_engagement(
    author: str | None,
    author_avgs: dict[str, float],
    global_reference: float,
) -> int:
    base_required = max(1, settings.trending_min_engagement_mix)
    ratio = 1.0
    if author and author in author_avgs and global_reference > 0:
        ratio = author_avgs[author] / global_reference
    ratio = max(settings.trend_author_scale_min, min(settings.trend_author_scale_max, ratio))
    required = round(base_required * ratio)
    return max(1, required)


def _normalize_terms(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    return [v.strip().lower() for v in values if v and v.strip()]


def _matches_priority(p: Post, keywords: list[str], watchlist: list[str]) -> bool:
    if not keywords or not watchlist:
        return False
    text = (p.text or "").lower()
    kw_match = any(term in text for term in keywords)
    if not kw_match:
        return False
    author = (p.author or "").lstrip("@").lower()
    return bool(author) and author in watchlist


def _normalize_hashtags(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    cleaned = []
    for v in values:
        if not v:
            continue
        cleaned_value = v.strip().lower().lstrip("#")
        if cleaned_value:
            cleaned.append(cleaned_value)
    return cleaned


def _matches_trending_hashtag(p: Post, hashtags: list[str]) -> bool:
    if not hashtags:
        return False
    text = (p.text or "").lower()
    if not text:
        return False
    return any(f"#{tag}" in text for tag in hashtags)


def rank_and_mark(
    recent_minutes: int | None = None,
    *,
    priority_keywords: Sequence[str] | None = None,
    priority_watchlist: Sequence[str] | None = None,
    trending_hashtags: Sequence[str] | None = None,
) -> int:
    now = datetime.utcnow()
    cutoff = None
    if recent_minutes is not None and recent_minutes > 0:
        cutoff = now - timedelta(minutes=recent_minutes)
    updated = 0
    keywords_norm = _normalize_terms(priority_keywords)
    watchlist_norm = _normalize_terms(priority_watchlist)
    hashtags_norm = _normalize_hashtags(trending_hashtags)
    expire_window = timedelta(minutes=max(settings.trend_expire_minutes, 0))
    with session_scope() as s:
        posts = s.execute(select(Post)).scalars().all()
        author_avgs, global_avg = _build_author_engagement_stats(posts)
        global_reference = max(global_avg, float(settings.trending_min_engagement_mix), 1.0)
        for p in posts:
            v, vel = compute_scores_for_post(p)
            created = as_utc_naive(p.created_at)
            if _matches_priority(p, keywords_norm, watchlist_norm):
                v = min(1.0, v + settings.profile_match_bonus)
            if _matches_trending_hashtag(p, hashtags_norm):
                v = min(1.0, v + settings.trending_hashtag_bonus)
            if settings.recency_bonus_minutes > 0 and settings.recency_bonus_amount > 0:
                if created and (now - created) <= timedelta(minutes=settings.recency_bonus_minutes):
                    v = min(1.0, v + settings.recency_bonus_amount)
            was_trending = p.trending
            ts = as_utc_naive(p.trending_since)
            candidate_ts = as_utc_naive(p.trending_candidate_since)
            if expire_window.total_seconds() > 0 and ts and (now - ts) >= expire_window:
                p.trending = False
                p.trending_since = None
                ts = None

            engagement_total = (p.like_count or 0) + (p.repost_count or 0) + (p.reply_count or 0)
            required_engagement = _required_engagement(p.author, author_avgs, global_reference)
            engagement_ok = engagement_total >= required_engagement
            qualifies = engagement_ok

            if cutoff is not None and created and created < cutoff:
                qualifies = False

            if cutoff is not None and candidate_ts and candidate_ts < cutoff:
                candidate_ts = None
                p.trending_candidate_since = None

            if qualifies:
                if candidate_ts is None and not p.trending:
                    candidate_ts = now
                    p.trending_candidate_since = now
            else:
                candidate_ts = None
                p.trending_candidate_since = None

            should_trend = False
            if p.trending and ts:
                should_trend = True
            elif candidate_ts and engagement_ok:
                should_trend = True

            trend_origin = ts or candidate_ts
            if should_trend and cutoff is not None and trend_origin and trend_origin < cutoff:
                should_trend = False

            p.virality_score = v
            p.velocity_score = vel

            if should_trend:
                if ts is None:
                    p.trending_since = trend_origin or now
                p.trending_candidate_since = None
            else:
                p.trending_since = None
                if not engagement_ok:
                    p.trending_candidate_since = None

            p.trending = should_trend
            if p.trending != was_trending:
                updated += 1
    return updated


def top_conversations(limit: int = 20, min_created_at: datetime | None = None) -> list[Post]:
    with session_scope() as s:
        stmt = select(Post)
        if min_created_at is not None:
            stmt = stmt.where(Post.created_at >= min_created_at)
        stmt = stmt.order_by(Post.trending.desc(), Post.virality_score.desc()).limit(limit)
        return s.execute(stmt).scalars().all()
