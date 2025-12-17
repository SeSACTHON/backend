from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Service Constants (Single Source of Truth)
# =============================================================================
SERVICE_NAME = "character-api"
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
    """Runtime configuration for the Character service."""

    app_name: str = "Character API"
    environment: str = "local"

    schema_reset_enabled: bool = Field(
        False,
        validation_alias=AliasChoices("CHARACTER_SCHEMA_RESET_ENABLED"),
        description="Allow destructive schema reset jobs (DROP/CREATE).",
    )
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ecoeco",
        description="PostgreSQL connection string for the shared ecoeco database.",
    )
    database_echo: bool = False

    auth_disabled: bool = Field(
        False,
        validation_alias=AliasChoices("CHARACTER_AUTH_DISABLED"),
        description="Skip access-token validation for local/manual testing.",
    )
    service_token_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CHARACTER_SERVICE_TOKEN_SECRET"),
        description="Shared secret used to authorize internal service-to-service calls.",
    )

    model_config = SettingsConfigDict(
        env_prefix="CHARACTER_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
