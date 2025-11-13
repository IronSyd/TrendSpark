from __future__ import annotations

import logging
import random
import threading
import time

try:
    import tweepy
except Exception:  # pragma: no cover - optional dependency
    tweepy = None  # type: ignore

from ..config import settings
from ..db import session_scope
from ..notifier import send_telegram_message
from ..ranking import compute_scores_for_post
from ..models import StreamRule
from ..growth import get_growth_state
from .ingest import upsert_post


log = logging.getLogger(__name__)


_stream_thread: threading.Thread | None = None
_stop_event = threading.Event()
_client: "TrendStream" | None = None
_user_cache: dict[str, str] = {}


def _build_default_rule() -> list[str]:
    keywords = get_growth_state().keywords or settings.keywords
    if not keywords:
        return []
    parts = [f'"{k}"' if " " in k else k for k in keywords]
    query = " OR ".join(parts)
    clause = query if len(parts) == 1 else f"({query})"
    return [f"{clause} lang:en -is:retweet"]


def _desired_rules() -> list[str]:
    with session_scope() as s:
        stored = s.query(StreamRule).order_by(StreamRule.created_at.asc()).all()
        if stored:
            return [rule.value for rule in stored]
    if settings.x_stream_rules:
        return settings.x_stream_rules
    return _build_default_rule()


def _ensure_rules(client: "TrendStream") -> bool:
    rules = _desired_rules()
    if not rules:
        log.warning(
            "X stream enabled but no rules available (set KEYWORDS or X_STREAM_RULES)"
        )
        return False
    try:
        existing = client.get_rules()
    except Exception as exc:
        log.error("Failed to fetch X stream rules: %s", exc)
        return False

    existing_map = {}
    if existing and existing.data:
        existing_map = {rule.value: rule.id for rule in existing.data}

    to_delete: list[str] = []
    for value, rule_id in existing_map.items():
        if value not in rules:
            to_delete.append(rule_id)

    if to_delete:
        try:
            client.delete_rules(to_delete)
            log.info("Removed %d obsolete X stream rules", len(to_delete))
        except Exception as exc:
            log.warning("Failed to delete X stream rules: %s", exc)

    to_add = [r for r in rules if r not in existing_map]
    if to_add:
        try:
            client.add_rules(
                [tweepy.StreamRule(value=r, tag="trend-spark") for r in to_add]
            )
            log.info("Added %d X stream rules", len(to_add))
        except Exception as exc:
            log.error("Failed to add X stream rules: %s", exc)
            return False

    return True


if tweepy is not None:  # pragma: no branch

    class TrendStream(tweepy.StreamingClient):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(
                bearer_token=settings.x_bearer_token,
                wait_on_rate_limit=True,
            )

        def on_tweet(self, tweet: tweepy.Tweet) -> None:  # type: ignore[name-defined]
            metrics = getattr(tweet, "public_metrics", None) or {}
            base_tweet = tweet
            author_id = getattr(tweet, "author_id", None)
            username = None

            if getattr(tweet, "referenced_tweets", None):
                for ref in tweet.referenced_tweets:
                    if getattr(ref, "type", None) == "retweeted":
                        try:
                            response = self.get_tweet(
                                ref.id,
                                expansions=["author_id"],
                                tweet_fields=["created_at", "public_metrics"],
                                user_fields=["username"],
                            )
                            if response and response.data:
                                original = response.data
                                base_tweet = original
                                metrics = (
                                    getattr(original, "public_metrics", None) or metrics
                                )
                                includes = getattr(response, "includes", None)
                                users = []
                                if includes:
                                    if isinstance(includes, dict):
                                        users = includes.get("users", []) or []
                                    else:
                                        users = getattr(includes, "users", []) or []
                                for user in users:
                                    try:
                                        uid = str(getattr(user, "id"))
                                        uname = getattr(user, "username", None)
                                        if uid and uname:
                                            _user_cache[uid] = uname
                                    except Exception:
                                        continue
                        except Exception:
                            pass
                        break

            if author_id is not None:
                key = str(author_id)
                if key in _user_cache:
                    username = _user_cache[key]
                else:
                    try:
                        user = self.get_user(id=author_id, user_fields=["username"])
                        if user and user.data and getattr(user.data, "username", None):
                            username = user.data.username
                            _user_cache[key] = username
                    except Exception:
                        username = None

            url_username = username or (
                str(author_id) if author_id is not None else None
            )
            if url_username:
                post_url = f"https://x.com/{url_username}/status/{base_tweet.id}"
            else:
                post_url = f"https://x.com/status/{base_tweet.id}"
            data = {
                "platform": "x",
                "post_id": str(base_tweet.id),
                "text": getattr(base_tweet, "text", None) or tweet.text,
                "author": username
                or (str(author_id) if author_id is not None else None),
                "created_at": getattr(base_tweet, "created_at", None),
                "like_count": int(metrics.get("like_count", 0)),
                "reply_count": int(metrics.get("reply_count", 0)),
                "repost_count": int(metrics.get("retweet_count", 0)),
                "quote_count": int(metrics.get("quote_count", 0)),
                "view_count": int(metrics.get("impression_count", 0)),
                "url": post_url,
            }

            trending_payload: dict | None = None
            with session_scope() as session:
                post = upsert_post(session, data)
                virality, velocity = compute_scores_for_post(post)
                was_trending = post.trending
                post.virality_score = virality
                post.velocity_score = velocity
                engagement_total = (
                    (post.like_count or 0)
                    + (post.reply_count or 0)
                    + (post.repost_count or 0)
                )
                post.trending = engagement_total >= settings.trending_min_engagement_mix

                if post.trending and not was_trending:
                    trending_payload = {
                        "url": post.url,
                        "text": post.text,
                        "score": virality,
                    }

            if trending_payload:
                snippet = (
                    trending_payload["url"] or (trending_payload["text"] or "")[:200]
                )
                message = f"🔥 Stream alert {trending_payload['score']:.2f}: {snippet}"
                send_telegram_message(message)

        def on_errors(self, errors):  # type: ignore[override]
            log.error("X stream error: %s", errors)
            return super().on_errors(errors)

        def on_connection_error(self):  # type: ignore[override]
            log.warning("X stream connection error; reconnecting")
            self.disconnect()

else:  # pragma: no cover

    TrendStream = None  # type: ignore[assignment]


def start_filtered_stream() -> None:
    global _stream_thread, _client

    if not settings.x_stream_enabled:
        return
    if tweepy is None:
        log.warning("tweepy not installed; cannot start X filtered stream")
        return
    if not settings.x_bearer_token:
        log.warning("X_STREAM_ENABLED set but X_BEARER_TOKEN missing; skipping stream")
        return
    if _stream_thread and _stream_thread.is_alive():
        return

    client = TrendStream()
    if not _ensure_rules(client):
        return

    _stop_event.clear()
    _client = client

    def _run_stream():
        nonlocal client  # allow reinitialising the client on hard failures
        global _client
        backoff = 5.0
        while not _stop_event.is_set():
            try:
                client.filter(
                    tweet_fields=["created_at", "public_metrics", "author_id"],
                    expansions=["author_id"],
                    user_fields=["username"],
                )
                backoff = 5.0
            except Exception as exc:
                if _stop_event.is_set():
                    break
                retry_backoff = min(backoff, 300.0)
                if tweepy is not None and isinstance(exc, tweepy.TooManyRequests):
                    log.warning(
                        "X stream rate limited; backing off %.1fs", retry_backoff
                    )
                    retry_backoff = min(retry_backoff * 2, 600.0)
                else:
                    log.warning(
                        "X stream exception; retrying in ~%.1fs: %s", retry_backoff, exc
                    )

                jitter = random.uniform(0.8, 1.4)
                time.sleep(retry_backoff * jitter)
                backoff = min(retry_backoff * 2, 600.0)

                try:
                    _ensure_rules(client)
                except Exception as rule_exc:
                    log.debug("Failed to refresh stream rules: %s", rule_exc)

                # attempt full reconnect if the client ended up closed
                try:
                    client.disconnect()
                except Exception:
                    pass
                try:
                    client = TrendStream()
                    if _ensure_rules(client):
                        _client = client
                except Exception as reconnect_exc:
                    log.error(
                        "Failed to reinitialise X stream client: %s", reconnect_exc
                    )

    _stream_thread = threading.Thread(
        target=_run_stream, name="XFilteredStream", daemon=True
    )
    _stream_thread.start()
    log.info("X filtered stream started")


def stop_filtered_stream() -> None:
    global _stream_thread, _client
    _stop_event.set()
    if _client:
        try:
            _client.disconnect()
        except Exception:
            pass
    if _stream_thread and _stream_thread.is_alive():
        _stream_thread.join(timeout=5)
    _stream_thread = None
    _client = None
    log.info("X filtered stream stopped")


def refresh_stream_rules() -> None:
    client = _client
    if client is None:
        return
    try:
        _ensure_rules(client)
    except Exception as exc:
        log.warning("Failed to refresh stream rules: %s", exc)
