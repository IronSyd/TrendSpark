from __future__ import annotations

from datetime import datetime, timezone


def as_utc_naive(dt: datetime | None) -> datetime | None:
    """Normalize datetimes so comparisons don't mix aware/naive values."""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


__all__ = ["as_utc_naive"]
