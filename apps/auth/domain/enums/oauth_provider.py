"""OAuth Provider Enum."""

from enum import Enum


class OAuthProvider(str, Enum):
    """지원하는 OAuth 프로바이더."""

    GOOGLE = "google"
    KAKAO = "kakao"
    NAVER = "naver"

    @classmethod
    def from_string(cls, value: str) -> "OAuthProvider":
        """문자열에서 OAuthProvider 생성.

        Raises:
            ValueError: 지원하지 않는 프로바이더
        """
        try:
            return cls(value.lower())
        except ValueError as e:
            supported = ", ".join(p.value for p in cls)
            raise ValueError(f"Unsupported provider: {value}. Supported: {supported}") from e
