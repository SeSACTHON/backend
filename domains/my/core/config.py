from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "My API"
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/my",
        description="SQLAlchemy URL used for the My service database.",
    )
    metrics_cache_ttl_seconds: int = 60
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "sesacthon-auth"
    jwt_audience: str = "sesacthon-clients"
    access_cookie_name: str = "s_access"

    model_config = SettingsConfigDict(
        env_prefix="MY_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
