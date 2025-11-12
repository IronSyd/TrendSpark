from __future__ import annotations

from typing import Iterable, Sequence

from fastapi import Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import settings
from .db import session_scope
from .security import (
    AuthenticatedUser,
    SeedToken,
    authenticate_token,
    ensure_seed_users,
    parse_seed_tokens,
    select_service_token,
)

EXEMPT_DEFAULT = {"/health", "/docs", "/openapi.json", "/redoc"}


def _extract_token(header_value: str) -> str | None:
    if not header_value:
        return None

    lowered = header_value.lower()
    if lowered.startswith("bearer "):
        return header_value[7:].strip()
    if lowered.startswith("token "):
        return header_value[6:].strip()
    return header_value.strip() or None


class ApiTokenMiddleware(BaseHTTPMiddleware):
    """Bearer-token auth middleware with RBAC user lookup."""

    def __init__(
        self,
        app,
        *,
        seed_tokens: Sequence[SeedToken] | None = None,
        exempt_path_prefixes: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._exempt_prefixes = {
            prefix.rstrip("/") for prefix in (exempt_path_prefixes or EXEMPT_DEFAULT)
        }
        self._seed_tokens = list(seed_tokens or [])

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/") or "/"
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in self._exempt_prefixes
        ):
            return await call_next(request)

        raw_header = request.headers.get("Authorization", "").strip()
        token = _extract_token(raw_header)
        if not token:
            return _unauthorized()

        with session_scope() as session:
            user = authenticate_token(session, token)

        if not user:
            return _unauthorized()

        request.state.user = user
        return await call_next(request)


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Unauthorized"},
    )


def get_current_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def require_roles(*roles: str):
    required = {role.lower() for role in roles if role}

    async def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if required and required.isdisjoint(user.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency


# Seed accounts derived from configuration.
SEED_TOKENS: list[SeedToken] = parse_seed_tokens(settings.api_tokens)
ensure_seed_users(SEED_TOKENS)

SERVICE_TOKEN: str | None = select_service_token(SEED_TOKENS)


__all__ = [
    "ApiTokenMiddleware",
    "AuthenticatedUser",
    "SERVICE_TOKEN",
    "SEED_TOKENS",
    "get_current_user",
    "require_roles",
]
