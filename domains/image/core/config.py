from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Service Constants (Single Source of Truth)
# =============================================================================
SERVICE_NAME = "image-api"
SERVICE_VERSION = "1.0.7"

# =============================================================================
# Logging Constants (12-Factor App Compliance)
# =============================================================================
ENV_KEY_ENVIRONMENT = "ENVIRONMENT"
ENV_KEY_LOG_LEVEL = "LOG_LEVEL"
ENV_KEY_LOG_FORMAT = "LOG_FORMAT"

DEFAULT_ENVIRONMENT = "dev"
DEFAULT_LOG_LEVEL = "DEBUG"
DEFAULT_LOG_FORMAT = "json"

ECS_VERSION = "8.11.0"

EXCLUDED_LOG_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "message",
    }
)


class Settings(BaseSettings):
    app_name: str = "Image API"
    auth_disabled: bool = Field(
        False,
        validation_alias=AliasChoices("IMAGE_AUTH_DISABLED"),
    )
    aws_region: str = Field(
        "ap-northeast-2",
        validation_alias=AliasChoices("IMAGE_AWS_REGION", "AWS_REGION"),
    )
    s3_bucket: str = Field(
        "dev-sesacthon-dev-images",
        validation_alias=AliasChoices("IMAGE_S3_BUCKET"),
    )
    cdn_domain: HttpUrl = Field(
        "https://images.dev.growbin.app",
        validation_alias=AliasChoices("IMAGE_CDN_DOMAIN"),
    )
    presign_expires_seconds: int = Field(
        900,
        ge=60,
        le=7 * 24 * 60 * 60,
        validation_alias=AliasChoices("IMAGE_PRESIGN_EXPIRES"),
    )
    redis_url: str = Field(
        "redis://localhost:6379/6",
        validation_alias=AliasChoices("IMAGE_REDIS_URL"),
    )
    upload_state_ttl: int = Field(
        900,
        ge=60,
        le=24 * 60 * 60,
        validation_alias=AliasChoices("IMAGE_UPLOAD_STATE_TTL"),
    )
    allowed_targets: tuple[Literal["chat", "scan", "my"], ...] = ("chat", "scan", "my")

    model_config = SettingsConfigDict(
        env_prefix="IMAGE_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
