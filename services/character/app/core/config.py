from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Character API"
    environment: str = "dev"

    database_url: str = (
        "postgresql+asyncpg://sesacthon:sesacthon@postgres-cluster.postgres.svc.cluster.local:5432/sesacthon"
    )

    max_catalog_items: int = 100
    classification_min_score: float = 0.7

    model_config = SettingsConfigDict(env_prefix="CHARACTER_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
