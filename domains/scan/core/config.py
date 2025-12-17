from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Service Constants (Single Source of Truth)
# =============================================================================
SERVICE_NAME = "scan-api"
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
    app_name: str = "Scan API"
    character_api_base_url: str = Field(
        "http://character-api.character.svc.cluster.local:8000",
        description="Base URL for the Character service (no trailing slash).",
    )
    character_grpc_target: str = Field(
        "character-grpc.character.svc.cluster.local:50051",
        description="gRPC target address for Character service (host:port).",
    )
    character_reward_endpoint: str = Field(
        "/api/v1/internal/characters/rewards",
        description="Path for the character reward evaluation endpoint.",
    )
    character_api_timeout_seconds: float = Field(
        30.0,
        ge=0.1,
        description="Timeout in seconds for Character service HTTP calls.",
    )
    character_api_token: str | None = Field(
        default=None,
        description="Optional bearer token for Character internal API authentication.",
    )
    reward_feature_enabled: bool = True
    auth_disabled: bool = Field(
        False,
        validation_alias=AliasChoices("SCAN_AUTH_DISABLED"),
        description="When true, skips token validation (use only for local dev).",
    )

    model_config = SettingsConfigDict(
        env_prefix="SCAN_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
