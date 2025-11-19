from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

from app.core.config import Settings, get_settings
from app.services.providers.base import OAuthProvider
from app.services.providers.google import GoogleOAuthProvider
from app.services.providers.kakao import KakaoOAuthProvider
from app.services.providers.naver import NaverOAuthProvider


class ProviderRegistry:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.providers: Mapping[str, OAuthProvider] = self._build()

    def _build(self) -> Mapping[str, OAuthProvider]:
        return {
            "kakao": KakaoOAuthProvider(
                client_id=self.settings.kakao_client_id,
                client_secret=self.settings.kakao_client_secret,
                redirect_uri=str(self.settings.kakao_redirect_uri)
                if self.settings.kakao_redirect_uri
                else None,
            ),
            "google": GoogleOAuthProvider(
                client_id=self.settings.google_client_id,
                client_secret=self.settings.google_client_secret,
                redirect_uri=str(self.settings.google_redirect_uri)
                if self.settings.google_redirect_uri
                else None,
            ),
            "naver": NaverOAuthProvider(
                client_id=self.settings.naver_client_id,
                client_secret=self.settings.naver_client_secret,
                redirect_uri=str(self.settings.naver_redirect_uri)
                if self.settings.naver_redirect_uri
                else None,
            ),
        }

    def get(self, provider: str) -> OAuthProvider:
        key = provider.lower()
        if key not in self.providers:
            raise ValueError(f"Unsupported provider: {provider}")
        return self.providers[key]

