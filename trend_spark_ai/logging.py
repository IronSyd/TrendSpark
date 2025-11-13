from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterable, Mapping, MutableMapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(value: str | None) -> None:
    _correlation_id_ctx.set(value)


def get_correlation_id(default: str | None = None) -> str | None:
    cid = _correlation_id_ctx.get()
    if cid is None and default:
        cid = default
        _correlation_id_ctx.set(cid)
    return cid


def new_correlation_id() -> str:
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: MutableMapping[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        for key, value in record.__dict__.items():
            if (
                key.startswith("_")
                or key in payload
                or key
                in (
                    "args",
                    "msg",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                )
            ):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False)


class CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


def configure_logging(level: str | None = None) -> None:
    configured_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    numeric = logging.getLevelName(configured_level)
    root = logging.getLogger()
    root.setLevel(numeric)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationFilter())
    root.addHandler(handler)


def inject_correlation_header(
    headers: Mapping[str, str] | None = None,
    *,
    header_name: str = "X-Request-ID",
) -> dict[str, str]:
    result: dict[str, str] = dict(headers or {})
    cid = get_correlation_id()
    if cid:
        result.setdefault(header_name, cid)
    return result


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        header_name: str = "X-Request-ID",
        skip_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.skip_paths = set(skip_paths or [])

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.skip_paths:
            return await call_next(request)

        incoming = request.headers.get(self.header_name) or new_correlation_id()
        token = _correlation_id_ctx.set(incoming)
        try:
            response = await call_next(request)
        finally:
            _correlation_id_ctx.reset(token)
        response.headers.setdefault(self.header_name, incoming)
        return response


@contextmanager
def correlation_context(correlation_id: str | None = None):
    cid = correlation_id or new_correlation_id()
    token = _correlation_id_ctx.set(cid)
    try:
        yield cid
    finally:
        _correlation_id_ctx.reset(token)
