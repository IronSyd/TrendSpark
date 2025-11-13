from __future__ import annotations
from typing import Iterable
from datetime import datetime, timezone
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

try:
    import praw
except Exception:
    praw = None  # type: ignore

from ..config import settings

log = logging.getLogger(__name__)


def fetch_reddit_trending(
    keywords: list[str], limit_per_sub: int = 25
) -> Iterable[dict]:
    """Fetch hot posts across relevant subreddits for given keywords."""
    if not settings.reddit_ingest_enabled:
        log.info("Reddit ingest disabled via configuration")
        return []
    if not (
        settings.reddit_client_id
        and settings.reddit_client_secret
        and settings.reddit_user_agent
    ):
        log.info("Reddit credentials not set; skipping Reddit ingestion")
        return []
    if praw is None:
        log.warning("praw not available; skipping Reddit ingestion")
        return []

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    # Heuristic: map keywords to a few subs; allow duplicates
    seed_subs = set()
    for k in keywords:
        k_low = k.lower()
        if k_low in {"ai", "artificial intelligence", "gpt", "llm"}:
            seed_subs.update(
                ["ArtificialInteligence", "MachineLearning", "OpenAI", "aidev"]
            )
        if k_low in {"marketing", "growth", "saas"}:
            seed_subs.update(["marketing", "Entrepreneur", "SaaS", "startup"])
        seed_subs.add(k_low)

    seen_ids: set[str] = set()
    for sub in seed_subs:
        try:
            posts = _fetch_subreddit_with_retry(reddit, sub, limit_per_sub)
            for post in posts:
                pid = f"{post.id}"
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                yield {
                    "platform": "reddit",
                    "post_id": pid,
                    "text": f"{post.title}\n\n{post.selftext[:500]}",
                    "author": str(post.author) if post.author else None,
                    "created_at": datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    ),
                    "like_count": int(post.score or 0),
                    "reply_count": int(post.num_comments or 0),
                    "repost_count": 0,
                    "quote_count": 0,
                    "view_count": 0,
                    "url": f"https://reddit.com{post.permalink}",
                }
        except Exception as e:
            log.warning("Failed subreddit %s: %s", sub, e)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _fetch_subreddit_with_retry(reddit: "praw.Reddit", subreddit: str, limit: int):
    return list(reddit.subreddit(subreddit).hot(limit=limit))
