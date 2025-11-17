import os
import warnings
from functools import lru_cache
from typing import List, Sequence

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    Field,
    PostgresDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = Field(default=None)
    x_bearer_token: str | None = Field(default=None)
    x_consumer_key: str | None = Field(default=None)
    x_consumer_secret: str | None = Field(default=None)
    x_access_token: str | None = Field(default=None)
    x_access_token_secret: str | None = Field(default=None)
    x_trends_woeid: int = Field(default=1)

    reddit_client_id: str | None = Field(default=None)
    reddit_client_secret: str | None = Field(default=None)
    reddit_user_agent: str | None = Field(default=None)

    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)

    database_url: PostgresDsn | str = Field(default="sqlite:///trend_spark.db")

    keywords: List[str] = Field(default_factory=list)
    tone_priorities: List[str] = Field(
        default_factory=lambda: ["witty", "helpful", "contrarian", "informative"],
    )
    watchlist: List[str] = Field(default_factory=list)
    x_stream_rules: List[str] = Field(default_factory=list)
    api_tokens: List[str] = Field(default_factory=list)
    api_rate_limits: List[str] = Field(
        default_factory=lambda: ["200/minute", "1000/day"]
    )

    niche_default: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NICHE", "NICHE_DEFAULT"),
    )
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )

    x_stream_enabled: bool = Field(default=False)
    x_ingest_enabled: bool = Field(default=True)
    reddit_ingest_enabled: bool = Field(default=True)
    ideas_time_hour: int = Field(default=8)
    alert_recency_minutes: int = Field(default=30)
    scheduler_url: AnyHttpUrl | str = Field(default="http://localhost:9000")
    trending_min_likes: int = Field(
        default=5,
        validation_alias=AliasChoices("TREND_MIN_LIKES", "TRENDING_MIN_LIKES"),
    )
    trending_min_responses: int = Field(
        default=3,
        validation_alias=AliasChoices("TREND_MIN_RESPONSES", "TRENDING_MIN_RESPONSES"),
    )
    trending_min_engagement_mix: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "TREND_MIN_ENGAGEMENT",
            "TRENDING_MIN_ENGAGEMENT",
            "TREND_MIN_ENGAGEMENT_MIX",
            "TRENDING_MIN_ENGAGEMENT_MIX",
        ),
    )
    trending_min_views: int = Field(
        default=500,
        validation_alias=AliasChoices("TREND_MIN_VIEWS", "TRENDING_MIN_VIEWS"),
    )
    trend_author_scale_min: float = Field(default=0.5)
    trend_author_scale_max: float = Field(default=2.5)
    profile_match_bonus: float = Field(default=0.1)
    trending_hashtag_bonus: float = Field(default=0.08)
    recency_bonus_minutes: int = Field(default=10)
    recency_bonus_amount: float = Field(default=0.05)
    trend_expire_minutes: int = Field(default=60)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator(
        "keywords",
        "tone_priorities",
        "watchlist",
        "api_tokens",
        "api_rate_limits",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: Sequence[str] | str | None) -> List[str]:
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @field_validator("x_stream_rules", mode="before")
    @classmethod
    def _split_semicolon(cls, value: Sequence[str] | str | None) -> List[str]:
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(";") if item.strip()]

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if item]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @field_validator("alert_recency_minutes")
    @classmethod
    def _validate_recency(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ALERT_RECENCY_MINUTES must be positive")
        return value

    @field_validator(
        "trending_min_likes",
        "trending_min_responses",
        "trending_min_engagement_mix",
        "trending_min_views",
        "recency_bonus_minutes",
        "trend_expire_minutes",
    )
    @classmethod
    def _validate_positive_int(cls, value: int, info) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value

    @field_validator("trend_author_scale_min", "trend_author_scale_max")
    @classmethod
    def _validate_author_scale(cls, value: float, info) -> float:
        if value <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return value

    @field_validator("profile_match_bonus")
    @classmethod
    def _validate_profile_bonus(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("PROFILE_MATCH_BONUS must be > 0")
        return value

    @field_validator("trending_hashtag_bonus")
    @classmethod
    def _validate_hashtag_bonus(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("TRENDING_HASHTAG_BONUS must be > 0")
        return value

    @field_validator("recency_bonus_amount")
    @classmethod
    def _validate_recency_bonus(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("RECENCY_BONUS_AMOUNT must be > 0")
        return value

    @field_validator("x_trends_woeid")
    @classmethod
    def _validate_woeid(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("X_TRENDS_WOEID must be positive")
        return value

    @model_validator(mode="after")
    def _verify_author_scale(self) -> "Settings":
        if self.trend_author_scale_max < self.trend_author_scale_min:
            raise ValueError("TREND_AUTHOR_SCALE_MAX must be >= TREND_AUTHOR_SCALE_MIN")
        return self

    @field_validator("api_tokens")
    @classmethod
    def _require_tokens(cls, value: List[str]) -> List[str]:
        if value:
            return value
        fallback = os.environ.get("DEFAULT_API_TOKEN", "local-test-token")
        warnings.warn(
            "API_TOKENS not set; falling back to DEFAULT_API_TOKEN/local-test-token. "
            "Set API_TOKENS in your environment for production deployments.",
            stacklevel=1,
        )
        return [fallback]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
