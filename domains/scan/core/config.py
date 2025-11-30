from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Scan API"
    character_api_base_url: str = Field(
        "http://character-api.character.svc.cluster.local:8000",
        description="Base URL for the Character service (no trailing slash).",
    )
    character_reward_endpoint: str = Field(
        "/api/v1/internal/characters/rewards",
        description="Path for the character reward evaluation endpoint.",
    )
    character_api_timeout_seconds: float = Field(
        5.0,
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

    jwt_secret_key: str = Field(
        "change-me",
        validation_alias=AliasChoices("SCAN_JWT_SECRET_KEY", "AUTH_JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = Field(
        "HS256",
        validation_alias=AliasChoices("SCAN_JWT_ALGORITHM", "AUTH_JWT_ALGORITHM"),
    )
    jwt_issuer: str = Field(
        "sesacthon-auth",
        validation_alias=AliasChoices("SCAN_JWT_ISSUER", "AUTH_JWT_ISSUER"),
    )
    jwt_audience: str = Field(
        "sesacthon-clients",
        validation_alias=AliasChoices("SCAN_JWT_AUDIENCE", "AUTH_JWT_AUDIENCE"),
    )
    access_cookie_name: str = Field(
        "s_access",
        validation_alias=AliasChoices("SCAN_ACCESS_COOKIE_NAME", "AUTH_ACCESS_COOKIE_NAME"),
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
