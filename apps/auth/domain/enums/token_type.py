"""Token Type Enum."""

from enum import Enum


class TokenType(str, Enum):
    """JWT 토큰 타입."""

    ACCESS = "access"
    REFRESH = "refresh"
