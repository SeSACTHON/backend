from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Service Constants (Single Source of Truth)
# =============================================================================
SERVICE_NAME = "location-api"
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
    app_name: str = "Location API"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/location"
    redis_url: str = "redis://localhost:6379/5"
    metrics_cache_ttl_seconds: int = 60
    auth_disabled: bool = Field(
        False,
        validation_alias=AliasChoices("LOCATION_AUTH_DISABLED"),
    )

    model_config = SettingsConfigDict(
        env_prefix="LOCATION_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
