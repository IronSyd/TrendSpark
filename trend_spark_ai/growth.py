from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import select

from .db import session_scope
from .models import GrowthConfig
from .config import settings


@dataclass
class GrowthState:
    id: int
    name: str
    niche: str | None
    keywords: list[str]
    watchlist: list[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


def _normalize_keywords(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    return [v.strip() for v in values if v and v.strip()]


def _to_state(cfg: GrowthConfig) -> GrowthState:
    return GrowthState(
        id=cfg.id,
        name=cfg.name or "Growth profile",
        niche=cfg.niche,
        keywords=_normalize_keywords(cfg.keywords),
        watchlist=_normalize_keywords(cfg.watchlist),
        is_default=cfg.is_default,
        is_active=cfg.is_active,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


def _ensure_default_profile(session) -> GrowthConfig:
    existing = session.execute(select(GrowthConfig.id)).scalar()
    if existing:
        profile = (
            session.query(GrowthConfig)
            .filter(GrowthConfig.is_active.is_(True))
            .order_by(GrowthConfig.is_default.desc(), GrowthConfig.created_at.desc())
            .first()
        )
        if profile and profile.is_default:
            return profile
        if profile and not profile.is_default:
            profile.is_default = True
            return profile
        # existing rows but all inactive; re-activate the newest
        fallback = (
            session.query(GrowthConfig)
            .order_by(GrowthConfig.created_at.desc())
            .first()
        )
        if fallback:
            fallback.is_active = True
            fallback.is_default = True
            return fallback
    profile = GrowthConfig(
        name="Default profile",
        is_default=True,
        is_active=True,
        niche=settings.niche_default,
        keywords=list(settings.keywords),
        watchlist=list(settings.watchlist),
    )
    session.add(profile)
    session.flush()
    return profile


def get_growth_state(profile_id: int | None = None, *, allow_inactive: bool = False) -> GrowthState:
    with session_scope() as s:
        _ensure_default_profile(s)
        query = s.query(GrowthConfig)
        if profile_id is not None:
            query = query.filter(GrowthConfig.id == profile_id)
            if not allow_inactive:
                query = query.filter(GrowthConfig.is_active.is_(True))
            cfg = query.first()
        else:
            cfg = (
                query.filter(GrowthConfig.is_active.is_(True), GrowthConfig.is_default.is_(True))
                .order_by(GrowthConfig.created_at.desc())
                .first()
            )
            if not cfg:
                cfg = (
                    query.filter(GrowthConfig.is_active.is_(True))
                    .order_by(GrowthConfig.created_at.desc())
                    .first()
                )
        if not cfg:
            raise ValueError("Growth profile not found")
        s.expunge(cfg)
    return _to_state(cfg)


def list_growth_profiles(*, include_inactive: bool = False) -> list[GrowthState]:
    with session_scope() as s:
        _ensure_default_profile(s)
        query = s.query(GrowthConfig)
        if not include_inactive:
            query = query.filter(GrowthConfig.is_active.is_(True))
        rows = (
            query.order_by(GrowthConfig.is_default.desc(), GrowthConfig.created_at.desc())
            .all()
        )
        return [_to_state(row) for row in rows]


def create_growth_profile(
    *,
    name: str,
    niche: str | None,
    keywords: Sequence[str],
    watchlist: Sequence[str],
    make_default: bool = False,
) -> GrowthState:
    keywords_norm = _normalize_keywords(keywords)
    watchlist_norm = _normalize_keywords(watchlist)
    niche_norm = niche.strip() if niche else None
    name_norm = name.strip() or "Growth profile"

    with session_scope() as s:
        _ensure_default_profile(s)
        profile = GrowthConfig(
            name=name_norm,
            niche=niche_norm,
            keywords=keywords_norm,
            watchlist=watchlist_norm,
            is_active=True,
            is_default=False,
        )
        if make_default:
            for row in s.query(GrowthConfig).filter(GrowthConfig.is_default.is_(True)):
                row.is_default = False
            profile.is_default = True
        s.add(profile)
        s.flush()
        s.refresh(profile)
        s.expunge(profile)
    return _to_state(profile)


def update_growth_profile(
    profile_id: int,
    *,
    name: str | None = None,
    niche: str | None = None,
    keywords: Sequence[str] | None = None,
    watchlist: Sequence[str] | None = None,
    is_active: bool | None = None,
    make_default: bool | None = None,
) -> GrowthState:
    with session_scope() as s:
        _ensure_default_profile(s)
        profile = s.get(GrowthConfig, profile_id)
        if not profile:
            raise ValueError("Growth profile not found")
        if name is not None:
            profile.name = name.strip() or profile.name
        if niche is not None:
            profile.niche = niche.strip() if niche else None
        if keywords is not None:
            profile.keywords = _normalize_keywords(keywords)
        if watchlist is not None:
            profile.watchlist = _normalize_keywords(watchlist)
        if is_active is not None:
            profile.is_active = is_active
        if make_default:
            for row in s.query(GrowthConfig).filter(GrowthConfig.is_default.is_(True)):
                if row.id != profile.id:
                    row.is_default = False
            profile.is_default = True
        s.flush()
        s.refresh(profile)
        s.expunge(profile)
    return _to_state(profile)


def set_default_growth_profile(profile_id: int) -> GrowthState:
    return update_growth_profile(profile_id, make_default=True, is_active=True)


def deactivate_growth_profile(profile_id: int) -> GrowthState:
    with session_scope() as s:
        _ensure_default_profile(s)
        profile = s.get(GrowthConfig, profile_id)
        if not profile:
            raise ValueError("Growth profile not found")
        if profile.is_default:
            raise ValueError("Cannot deactivate the default growth profile")
        profile.is_active = False
        s.flush()
        s.refresh(profile)
        s.expunge(profile)
    return _to_state(profile)


def update_growth_state(
    *,
    niche: str | None,
    keywords: Sequence[str],
    watchlist: Sequence[str],
    profile_id: int | None = None,
) -> GrowthState:
    target = get_growth_state(profile_id, allow_inactive=True)
    return update_growth_profile(
        target.id,
        niche=niche,
        keywords=keywords,
        watchlist=watchlist,
    )
