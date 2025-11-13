from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Sequence
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

try:
    import tweepy
except Exception:  # library not installed yet or optional
    tweepy = None

from ..config import settings
from ..db import session_scope
from ..models import IngestionState


log = logging.getLogger(__name__)


_client_cache: dict[str, "tweepy.Client"] = {}
_trends_api_cache: dict[str, "tweepy.API"] = {}
_STATE_KEY_SINCE_ID = "x_since_id"
_TREND_CACHE_KEY = "default"
_TREND_CACHE_TTL = timedelta(minutes=10)
_trending_cache: dict[str, tuple[list[str], datetime]] = {}


def _get_client() -> "tweepy.Client" | None:
    if not settings.x_bearer_token or tweepy is None:
        return None
    if "default" not in _client_cache:
        _client_cache["default"] = tweepy.Client(
            bearer_token=settings.x_bearer_token,
            wait_on_rate_limit=True,
        )
    return _client_cache["default"]


def _get_trends_api() -> "tweepy.API" | None:
    if tweepy is None:
        return None
    if not all(
        [
            settings.x_consumer_key,
            settings.x_consumer_secret,
            settings.x_access_token,
            settings.x_access_token_secret,
        ]
    ):
        return None
    if "default" in _trends_api_cache:
        return _trends_api_cache["default"]
    handler_cls = getattr(tweepy, "OAuth1UserHandler", None) or getattr(
        tweepy, "OAuthHandler", None
    )
    if handler_cls is None:
        return None
    auth = handler_cls(
        settings.x_consumer_key,
        settings.x_consumer_secret,
        settings.x_access_token,
        settings.x_access_token_secret,
    )
    api = tweepy.API(auth, wait_on_rate_limit=True)
    _trends_api_cache["default"] = api
    return api


def search_recent_tweets(
    keywords: list[str], max_results: int = 50
) -> Iterator[dict[str, Any]]:
    """Search recent tweets for given keywords using X API v2.
    Requires X_BEARER_TOKEN. Returns iterator of tweet dicts with metrics.
    """
    if max_results <= 0:
        return

    client = _get_client()
    if client is None:
        log.info("X_BEARER_TOKEN not set; skipping X ingestion")
        return

    # Build simple OR query over keywords, excluding retweets
    query = (
        " OR ".join([f'"{k}"' if " " in k else k for k in keywords])
        + " -is:retweet lang:en"
    )
    max_results = min(max(10, max_results), 100)
    since_id = _get_since_id()
    params = {
        "query": query,
        "tweet_fields": [
            "created_at",
            "public_metrics",
            "lang",
            "entities",
            "possibly_sensitive",
            "referenced_tweets",
        ],
        "expansions": [
            "author_id",
            "referenced_tweets.id",
            "referenced_tweets.id.author_id",
        ],
        "user_fields": ["username"],
        "max_results": max_results,
    }

    if since_id:
        params["since_id"] = since_id
    else:
        end_time = datetime.now(timezone.utc) - timedelta(seconds=15)
        start_time = end_time - timedelta(hours=6)
        params["start_time"] = start_time
        params["end_time"] = end_time

    try:
        tweets = _search_recent_with_retry(client, params)
    except tweepy.TooManyRequests as exc:
        log.warning("Hit X search rate limit; backing off: %s", exc)
        return
    except Exception as exc:
        log.warning("Failed to fetch recent tweets: %s", exc)
        return

    if not tweets.data:
        return

    includes = getattr(tweets, "includes", {}) or {}
    if isinstance(includes, dict):
        users = includes.get("users", [])
        included_tweets = includes.get("tweets", [])
    else:
        users = getattr(includes, "users", []) or []
        included_tweets = getattr(includes, "tweets", []) or []
    user_map: dict[str, str] = {}
    for user in users:
        try:
            user_id = str(getattr(user, "id"))
            username = getattr(user, "username", None)
            if user_id and username:
                user_map[user_id] = username
        except Exception:
            continue
    tweet_map: dict[str, tweepy.Tweet] = {}
    for inc in included_tweets:
        try:
            tweet_map[str(getattr(inc, "id"))] = inc
        except Exception:
            continue

    max_id: int | None = None
    # Map tweets into unified dict format
    for t in tweets.data:
        m = t.public_metrics or {}
        try:
            t_id = int(t.id)
            max_id = t_id if max_id is None else max(max_id, t_id)
        except Exception:
            max_id = max_id

        base_tweet = t
        metrics = m
        if getattr(t, "referenced_tweets", None):
            for ref in t.referenced_tweets:
                if getattr(ref, "type", None) == "retweeted":
                    original = tweet_map.get(str(ref.id))
                    if original is not None:
                        base_tweet = original
                        metrics = original.public_metrics or metrics
                    break

        author_id = getattr(base_tweet, "author_id", None)
        author_str = str(author_id) if author_id is not None else None
        username = user_map.get(author_str) if author_str else None
        if username:
            post_url = f"https://x.com/{username}/status/{base_tweet.id}"
        elif author_str:
            post_url = f"https://x.com/{author_str}/status/{base_tweet.id}"
        else:
            post_url = f"https://x.com/status/{base_tweet.id}"
        yield {
            "platform": "x",
            "post_id": str(base_tweet.id),
            "text": getattr(base_tweet, "text", t.text),
            "author": username or author_str,
            "created_at": getattr(base_tweet, "created_at", None),
            "like_count": int(metrics.get("like_count", 0)),
            "reply_count": int(metrics.get("reply_count", 0)),
            "repost_count": int(metrics.get("retweet_count", 0)),
            "quote_count": int(metrics.get("quote_count", 0)),
            "view_count": (
                int(metrics.get("impression_count", 0))
                if "impression_count" in metrics
                else 0
            ),
            "url": post_url,
        }

    if max_id is not None:
        _set_since_id(str(max_id))


def fetch_tweet_metrics(tweet_ids: Sequence[str]) -> dict[str, dict[str, Any]] | None:
    """Fetch metrics for given tweet IDs. Returns mapping id -> metrics."""
    ids = [tid for tid in tweet_ids if tid]
    if not ids:
        return {}
    client = _get_client()
    if client is None:
        log.info("X metrics requested but bearer token missing or tweepy unavailable")
        return None

    try:
        resp = _get_tweets_with_retry(client, ids)
    except tweepy.TooManyRequests as exc:
        log.warning("Hit X metrics rate limit; backing off: %s", exc)
        return {}
    except Exception as exc:
        log.warning("Failed to fetch tweet metrics: %s", exc)
        return {}
    if not resp.data:
        return {}

    result: dict[str, dict[str, Any]] = {}
    for item in resp.data:
        metrics = item.public_metrics or {}
        result[str(item.id)] = {
            "like_count": int(metrics.get("like_count", 0)),
            "reply_count": int(metrics.get("reply_count", 0)),
            "repost_count": int(metrics.get("retweet_count", 0)),
            "quote_count": int(metrics.get("quote_count", 0)),
            "created_at": item.created_at,
        }
    return result


def _get_since_id() -> str | None:
    with session_scope() as s:
        state = (
            s.query(IngestionState)
            .filter(IngestionState.key == _STATE_KEY_SINCE_ID)
            .first()
        )
        return state.value if state else None


def _set_since_id(value: str) -> None:
    with session_scope() as s:
        state = (
            s.query(IngestionState)
            .filter(IngestionState.key == _STATE_KEY_SINCE_ID)
            .first()
        )
        if state:
            state.value = value
        else:
            s.add(IngestionState(key=_STATE_KEY_SINCE_ID, value=value))


_retry_kwargs: dict[str, Any] = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=30),
    "reraise": True,
}
if tweepy is not None:
    _retry_kwargs["retry"] = retry_if_exception_type(tweepy.TooManyRequests)


@retry(**_retry_kwargs)
def _search_recent_with_retry(client: "tweepy.Client", params: dict[str, Any]):
    return client.search_recent_tweets(**params)


@retry(**_retry_kwargs)
def _get_tweets_with_retry(client: "tweepy.Client", ids: Sequence[str]):
    return client.get_tweets(
        ids=ids,
        tweet_fields=["public_metrics", "created_at"],
    )


def fetch_trending_hashtags(limit: int = 20) -> list[str]:
    """Fetch trending hashtags for weighting.

    Requires OAuth1 credentials and returns lowercase hashtag names without
    the leading '#'.
    """
    limit = max(1, min(limit, 50))
    cache_entry = _trending_cache.get(_TREND_CACHE_KEY)
    now = datetime.utcnow()
    if cache_entry:
        cached_values, cached_at = cache_entry
        if now - cached_at <= _TREND_CACHE_TTL:
            return cached_values[:limit]
    api = _get_trends_api()
    if api is None:
        return []
    try:
        results = api.get_place_trends(id=settings.x_trends_woeid)
    except Exception as exc:
        log.warning("Unable to fetch X trending hashtags: %s", exc)
        return []
    hashtags: list[str] = []
    try:
        if results:
            trends = results[0].get("trends", [])
            for item in trends:
                name = item.get("name")
                if not name or not name.startswith("#"):
                    continue
                cleaned = name.lstrip("#").strip().lower()
                if cleaned:
                    hashtags.append(cleaned)
                if len(hashtags) >= limit:
                    break
    except Exception as exc:
        log.warning("Malformed trends payload: %s", exc)
        return []
    _trending_cache[_TREND_CACHE_KEY] = (hashtags, now)
    return hashtags[:limit]
