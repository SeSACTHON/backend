"""TokenPayload Value Object."""

from __future__ import annotations

from dataclasses import dataclass

from auth.domain.enums.token_type import TokenType
from auth.domain.value_objects.base import ValueObject
from auth.domain.value_objects.user_id import UserId


@dataclass(frozen=True, slots=True)
class TokenPayload(ValueObject):
    """JWT 토큰 페이로드 Value Object.

    디코딩된 JWT 토큰의 정보를 담습니다.
    """

    user_id: UserId
    jti: str
    token_type: TokenType
    exp: int  # Unix timestamp
    iat: int  # Unix timestamp
    provider: str

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        """딕셔너리에서 TokenPayload 생성."""
        return cls(
            user_id=UserId.from_string(data["sub"]),
            jti=data["jti"],
            token_type=TokenType(data["type"]),
            exp=data["exp"],
            iat=data["iat"],
            provider=data["provider"],
        )

    @property
    def is_expired(self) -> bool:
        """토큰 만료 여부."""
        import time

        return time.time() > self.exp
