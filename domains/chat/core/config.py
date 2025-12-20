"""
Runtime Settings (FastAPI Official Pattern)

환경변수 기반 동적 설정 - 배포 환경별로 변경됨
Reference: https://fastapi.tiangolo.com/advanced/settings/
"""

from functools import lru_cache
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Chat service."""

    # ==========================================================================
    # 서비스 기본 정보
    # ==========================================================================

    app_name: str = "Chat API"

    # ==========================================================================
    # 인증 설정
    # ==========================================================================

    auth_disabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("CHAT_AUTH_DISABLED", "AUTH_DISABLED"),
        description="인증 비활성화 (로컬 테스트용)",
    )

    # ==========================================================================
    # CORS 설정
    # ==========================================================================

    cors_origins: List[str] = Field(
        default=[
            "https://frontend.dev.growbin.app",
            "https://frontend1.dev.growbin.app",
            "https://frontend2.dev.growbin.app",
            "http://localhost:5173",
            "https://localhost:5173",
        ],
        validation_alias=AliasChoices("CHAT_CORS_ORIGINS", "CORS_ORIGINS"),
        description="허용된 CORS origins (콤마 구분 문자열 또는 JSON 배열)",
    )

    cors_allow_credentials: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_CORS_ALLOW_CREDENTIALS"),
    )

    # ==========================================================================
    # OpenAI 설정 (향후 모델명 외부화용)
    # ==========================================================================

    # NOTE: 현재 모델명은 _shared/waste_pipeline에서 관리
    # 추후 chat 전용 모델 설정이 필요하면 여기에 추가

    model_config = SettingsConfigDict(
        env_prefix="CHAT_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (FastAPI pattern)."""
    return Settings()
