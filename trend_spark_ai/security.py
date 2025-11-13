from __future__ import annotations

import hashlib
from dataclasses import dataclass
import ast
import json
from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import Base, engine, session_scope
from .models import Role, User, UserRole


@dataclass(frozen=True)
class SeedToken:
    token: str
    roles: list[str]
    name: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    name: str | None
    label: str | None
    roles: set[str]


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_seed_tokens(entries: Sequence[str | dict]) -> list[SeedToken]:
    seeds: list[SeedToken] = []
    for raw in entries:
        if raw is None:
            continue
        if isinstance(raw, dict):
            token = str(raw.get("token", "")).strip()
            if not token:
                continue
            name = raw.get("name") or raw.get("label")
            raw_roles = raw.get("roles") or ["admin"]
            if isinstance(raw_roles, str):
                roles = [r.strip() for r in raw_roles.split("|") if r.strip()]
            else:
                roles = [str(r).strip() for r in raw_roles if str(r).strip()]
            seeds.append(
                SeedToken(
                    token=token,
                    roles=_ensure_roles(roles),
                    name=name,
                    label=raw.get("label"),
                )
            )
            continue

        value = str(raw).strip()
        if not value:
            continue
        if value.startswith("{") or value.startswith("["):
            parsed = None
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    parsed = None
            if isinstance(parsed, dict):
                seeds.extend(parse_seed_tokens([parsed]))
                continue
            if isinstance(parsed, list):
                seeds.extend(parse_seed_tokens(parsed))
                continue
        parts = value.split(":")
        parsed_token: str
        parsed_name: str | None = None
        parsed_roles: list[str]
        if len(parts) == 3:
            parsed_name, roles_str, parsed_token = parts
            parsed_roles = [p.strip() for p in roles_str.split("|") if p.strip()]
        elif len(parts) == 2:
            role_str, parsed_token = parts
            parsed_roles = [p.strip() for p in role_str.split("|") if p.strip()]
            parsed_name = role_str
        else:
            parsed_token = parts[0]
            parsed_roles = ["admin"]
        seeds.append(
            SeedToken(
                token=parsed_token,
                roles=_ensure_roles(parsed_roles),
                name=parsed_name,
            )
        )
    return seeds


def ensure_seed_users(seeds: Sequence[SeedToken]) -> None:
    if not seeds:
        return
    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        for seed in seeds:
            _ensure_user(session, seed)


def select_service_token(seeds: Sequence[SeedToken]) -> str | None:
    priority = ("service", "worker", "admin")
    for role in priority:
        for seed in seeds:
            if role in seed.roles:
                return seed.token
    return seeds[0].token if seeds else None


def authenticate_token(session: Session, token: str) -> AuthenticatedUser | None:
    token_hash = hash_token(token)
    stmt = (
        select(User)
        .where(User.token_hash == token_hash, User.is_active.is_(True))
        .limit(1)
    )
    user = session.execute(stmt).scalar_one_or_none()
    if not user:
        return None

    if user.roles:
        role_names = {role.name for role in user.roles}
    else:
        role_names = set()

    user.last_used_at = datetime.utcnow()
    session.add(user)

    return AuthenticatedUser(
        id=user.id,
        name=user.name,
        label=user.label,
        roles=role_names,
    )


def _ensure_user(session: Session, seed: SeedToken) -> None:
    token_hash = hash_token(seed.token)
    user = session.execute(
        select(User).where(User.token_hash == token_hash)
    ).scalar_one_or_none()

    if user is None:
        user = User(
            name=seed.name,
            label=seed.label or seed.name,
            token_hash=token_hash,
            is_active=True,
        )
        session.add(user)
        session.flush()
    else:
        if seed.name and user.name != seed.name:
            user.name = seed.name
        if (seed.label or seed.name) and user.label != (seed.label or seed.name):
            user.label = seed.label or seed.name
        session.add(user)

    target_roles = {role_name.lower() for role_name in seed.roles if role_name}
    existing_roles = set(
        session.execute(
            select(Role.name)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user.id)
        ).scalars()
    )

    for role_name in target_roles:
        if role_name in existing_roles:
            continue
        role = _get_or_create_role(session, role_name)
        _add_user_role(session, user.id, role.id)


def _get_or_create_role(session: Session, role_name: str) -> Role:
    stmt = select(Role).where(Role.name == role_name)
    role = session.execute(stmt).scalar_one_or_none()
    if role:
        return role

    role = Role(name=role_name)
    session.add(role)
    session.flush()
    return role


def _ensure_roles(roles: Iterable[str]) -> list[str]:
    cleaned = [r.lower() for r in roles if r]
    return cleaned or ["admin"]


def _add_user_role(session: Session, user_id: int, role_id: int) -> None:
    assigned_at = datetime.utcnow()
    dialect = session.bind.dialect.name if session.bind else ""
    params = {"user_id": user_id, "role_id": role_id, "assigned_at": assigned_at}

    if dialect == "postgresql":
        session.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id, assigned_at) "
                "VALUES (:user_id, :role_id, :assigned_at) "
                "ON CONFLICT (user_id, role_id) DO NOTHING"
            ),
            params,
        )
    elif dialect == "sqlite":
        session.execute(
            text(
                "INSERT OR IGNORE INTO user_roles (user_id, role_id, assigned_at) "
                "VALUES (:user_id, :role_id, :assigned_at)"
            ),
            params,
        )
    else:
        existing = session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        ).scalar_one_or_none()
        if not existing:
            session.add(
                UserRole(user_id=user_id, role_id=role_id, assigned_at=assigned_at)
            )
