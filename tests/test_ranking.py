import os
import math
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///./tests_unit.db")

from trend_spark_ai.ranking import compute_scores_for_post


def make_post(**overrides):
    defaults = dict(
        like_count=0,
        repost_count=0,
        quote_count=0,
        reply_count=0,
        view_count=0,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_compute_scores_increase_with_engagement():
    base_post = make_post()
    engaged_post = make_post(
        like_count=120,
        repost_count=35,
        quote_count=10,
        reply_count=45,
        view_count=10000,
    )

    base_virality, base_velocity = compute_scores_for_post(base_post)
    engaged_virality, engaged_velocity = compute_scores_for_post(engaged_post)

    assert engaged_virality > base_virality
    assert engaged_velocity > base_velocity


def test_velocity_penalises_stale_content():
    metrics = dict(
        like_count=25,
        repost_count=8,
        quote_count=4,
        reply_count=12,
        view_count=5500,
    )
    recent_post = make_post(created_at=datetime.now(timezone.utc), **metrics)
    stale_post = make_post(created_at=datetime.now(timezone.utc) - timedelta(hours=48), **metrics)

    recent_virality, recent_velocity = compute_scores_for_post(recent_post)
    stale_virality, stale_velocity = compute_scores_for_post(stale_post)

    assert math.isclose(recent_virality, stale_virality, rel_tol=1e-6)
    assert stale_velocity < recent_velocity
