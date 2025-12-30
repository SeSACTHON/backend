"""OAuth Provider Registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.auth.infrastructure.oauth.google import GoogleOAuthProvider
from apps.auth.infrastructure.oauth.kakao import KakaoOAuthProvider
from apps.auth.infrastructure.oauth.naver import NaverOAuthProvider

if TYPE_CHECKING:
    from apps.auth.infrastructure.oauth.base import OAuthProvider
    from apps.auth.setup.config import Settings


class ProviderRegistry:
    """OAuth 프로바이더 레지스트리."""

    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._providers: dict[str, OAuthProvider] = self._build()

    def _build(self) -> dict[str, "OAuthProvider"]:
        """프로바이더 인스턴스 생성."""
        providers = {}

        # Google
        if self._settings.google_client_id:
            providers["google"] = GoogleOAuthProvider(
                client_id=self._settings.google_client_id,
                client_secret=self._settings.google_client_secret,
                redirect_uri=self._settings.google_redirect_uri,
            )

        # Kakao
        if self._settings.kakao_client_id:
            providers["kakao"] = KakaoOAuthProvider(
                client_id=self._settings.kakao_client_id,
                client_secret=self._settings.kakao_client_secret,
                redirect_uri=self._settings.kakao_redirect_uri,
            )

        # Naver
        if self._settings.naver_client_id:
            providers["naver"] = NaverOAuthProvider(
                client_id=self._settings.naver_client_id,
                client_secret=self._settings.naver_client_secret,
                redirect_uri=self._settings.naver_redirect_uri,
            )

        return providers

    def get(self, provider: str) -> "OAuthProvider":
        """프로바이더 조회."""
        key = provider.lower()
        if key not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ValueError(f"Unsupported provider: {provider}. Available: {available}")
        return self._providers[key]

    @property
    def available_providers(self) -> list[str]:
        """사용 가능한 프로바이더 목록."""
        return list(self._providers.keys())
