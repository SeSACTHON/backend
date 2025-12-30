"""OAuth Provider Implementations."""

from apps.auth.infrastructure.oauth.base import OAuthProvider, OAuthProviderError
from apps.auth.infrastructure.oauth.google import GoogleOAuthProvider
from apps.auth.infrastructure.oauth.kakao import KakaoOAuthProvider
from apps.auth.infrastructure.oauth.naver import NaverOAuthProvider
from apps.auth.infrastructure.oauth.registry import ProviderRegistry
from apps.auth.infrastructure.oauth.client import OAuthClientImpl

__all__ = [
    "OAuthProvider",
    "OAuthProviderError",
    "GoogleOAuthProvider",
    "KakaoOAuthProvider",
    "NaverOAuthProvider",
    "ProviderRegistry",
    "OAuthClientImpl",
]
