"""OAuth provider enum."""

from __future__ import annotations

from enum import Enum


class OAuthProvider(str, Enum):
    """OAuth 프로바이더."""

    GOOGLE = "google"
    KAKAO = "kakao"
    NAVER = "naver"
