import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./tests_unit.db")

from trend_spark_ai.ingestion.ingest import upsert_post, _normalize_datetime
from trend_spark_ai.models import Base, Post


def create_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return Session()


def test_upsert_post_inserts_and_updates():
    session = create_session()
    data = {
        "platform": "x",
        "post_id": "123",
        "author": "@engage_bot",
        "url": "https://x.com/engage_bot/status/123",
        "text": "Hello world",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "like_count": 5,
        "reply_count": 2,
        "repost_count": 1,
        "quote_count": 0,
        "view_count": 40,
    }

    post = upsert_post(session, data)
    session.commit()

    assert post.id is not None
    assert post.author == "engage_bot"
    assert post.like_count == 5

    updated = data | {"like_count": 20, "reply_count": 5}
    post_again = upsert_post(session, updated)
    session.commit()

    assert post_again.id == post.id
    assert post_again.like_count == 20
    assert post_again.reply_count == 5


def test_normalize_datetime_parses_strings():
    iso_value = "2025-01-01T12:30:00+00:00"
    result = _normalize_datetime(iso_value)
    assert result == datetime(2025, 1, 1, 12, 30)
