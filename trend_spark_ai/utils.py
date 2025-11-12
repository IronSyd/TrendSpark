from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

