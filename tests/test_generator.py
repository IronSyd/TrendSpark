import os
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./tests_unit.db")

from trend_spark_ai import generator  # noqa: E402
from trend_spark_ai.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)


class StubCompletions:
    def __init__(self, payload):
        self._payload = payload

    def create(self, **_: dict):
        message = SimpleNamespace(content=json.dumps(self._payload))
        usage = SimpleNamespace(total_tokens=42)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class StubChat:
    def __init__(self, payload):
        self.completions = StubCompletions(payload)


class StubClient:
    def __init__(self, payload):
        self.chat = StubChat(payload)


@pytest.fixture(autouse=True)
def patch_adaptive_reply_tones(monkeypatch):
    monkeypatch.setattr(generator, "adaptive_reply_tones", lambda tones: list(tones))


def test_craft_replies_uses_openai_stub(monkeypatch):
    payload = {"replies": [{"tone": "witty", "reply": "Hello there"}]}
    stub_client = StubClient(payload)

    monkeypatch.setattr(generator, "_openai_client", lambda: stub_client)

    captured = {}

    def fake_record(kind, tokens=None):
        captured["kind"] = kind
        captured["tokens"] = tokens

    monkeypatch.setattr(generator, "record_openai_usage", fake_record)

    post = SimpleNamespace(
        text="Sample post",
        created_at=datetime.now(timezone.utc),
    )

    replies = generator.craft_replies_for_post(post, ["witty"])

    assert replies == [{"tone": "witty", "reply": "Hello there"}]
    assert captured == {"kind": "reply_suggestions", "tokens": 42}


def test_craft_replies_handles_invalid_json(monkeypatch):
    class BadStub:
        def __init__(self):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: SimpleNamespace(
                        choices=[
                            SimpleNamespace(message=SimpleNamespace(content="not json"))
                        ],
                        usage=SimpleNamespace(total_tokens=None),
                    )
                )
            )

    monkeypatch.setattr(generator, "_openai_client", lambda: BadStub())

    post = SimpleNamespace(
        text="Sample post",
        created_at=datetime.now(timezone.utc),
    )

    replies = generator.craft_replies_for_post(post, ["witty"])
    assert replies == []
