from __future__ import annotations
import logging

import httpx

from .config import settings
from .db import session_scope
from .logging import inject_correlation_header
from .metrics import record_alert_delivery
from .models import Notification

log = logging.getLogger(__name__)


def send_telegram_message(text: str, category: str | None = None, payload: dict | None = None) -> bool:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        log.info("Telegram settings missing; skip notify")
        record_alert_delivery("telegram", category, "skipped")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        headers = inject_correlation_header({"Content-Type": "application/json"})
        response = httpx.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
    except Exception as exc:
        log.warning("Failed to send Telegram message: %s", exc)
        record_alert_delivery("telegram", category, "error")
        return False

    with session_scope() as s:
        s.add(
            Notification(
                channel="telegram",
                category=category,
                message=text,
                payload=payload,
            )
        )
    record_alert_delivery("telegram", category, "sent")
    log.info(
        "telegram.sent",
        extra={
            "category": category,
            "length": len(text),
        },
    )
    return True
