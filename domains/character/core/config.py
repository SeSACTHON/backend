from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Character service."""

    app_name: str = "Character API"
    environment: str = "local"

    database_url: str = "sqlite+aiosqlite:///./character.db"
    database_echo: bool = False

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "sesacthon-auth"
    jwt_audience: str = "sesacthon-clients"

    access_cookie_name: str = "s_access"

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
