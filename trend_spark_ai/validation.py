from __future__ import annotations

import re
from typing import Iterable, Sequence


def sanitize_text(
    value: str | None, *, max_length: int, strip: bool = True
) -> str | None:
    """Trim and validate optional text payloads."""
    if value is None:
        return None
    if strip:
        value = value.strip()
    if not value:
        return None
    if len(value) > max_length:
        raise ValueError(f"value exceeds maximum length of {max_length} characters")
    return value


def sanitize_string_list(
    value: Sequence[str] | str | None,
    *,
    max_items: int,
    max_length: int,
    pattern: re.Pattern[str] | None = None,
    lower: bool = False,
) -> list[str]:
    """Normalise a list of strings, enforcing item counts and allowed characters."""
    if value is None:
        return []

    if isinstance(value, str):
        items = [value]
    else:
        items = list(value)

    cleaned: list[str] = []
    for item in items:
        item_str = str(item).strip()
        if not item_str:
            continue
        if len(item_str) > max_length:
            raise ValueError(f"'{item_str}' exceeds maximum length of {max_length}")
        if pattern and not pattern.fullmatch(item_str):
            raise ValueError(f"'{item_str}' contains invalid characters")
        cleaned.append(item_str.lower() if lower else item_str)

    if len(cleaned) > max_items:
        raise ValueError(f"too many items (max {max_items})")

    return cleaned


def sanitize_identifier(
    value: str, *, pattern: re.Pattern[str], max_length: int, strip: bool = True
) -> str:
    """Ensure identifiers use safe characters and length."""
    if strip:
        value = value.strip()
    if not value:
        raise ValueError("value cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"value exceeds maximum length of {max_length}")
    if not pattern.fullmatch(value):
        raise ValueError("value contains invalid characters")
    return value


def sanitize_identifier_list(
    values: Iterable[str],
    *,
    pattern: re.Pattern[str],
    max_length: int,
    max_items: int,
) -> list[str]:
    cleaned = []
    for raw in values:
        cleaned.append(sanitize_identifier(raw, pattern=pattern, max_length=max_length))
    if not cleaned:
        raise ValueError("at least one identifier must be supplied")
    if len(cleaned) > max_items:
        raise ValueError(f"too many identifiers (max {max_items})")
    return cleaned


def sanitize_handles(
    value: Sequence[str] | str | None,
    *,
    max_items: int,
    max_length: int,
) -> list[str]:
    handle_pattern = re.compile(r"^@?[A-Za-z0-9_]{1," + str(max_length) + r"}$")
    handles = sanitize_string_list(
        value,
        max_items=max_items,
        max_length=max_length,
        pattern=handle_pattern,
        lower=True,
    )
    normalized = []
    for handle in handles:
        normalized.append(handle.lstrip("@"))
    return normalized


def sanitize_optional_identifier(
    value: str | None,
    *,
    pattern: re.Pattern[str],
    max_length: int,
) -> str | None:
    if value is None:
        return None
    return sanitize_identifier(value, pattern=pattern, max_length=max_length)
