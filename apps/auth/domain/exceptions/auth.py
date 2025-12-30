"""Auth Domain Exceptions."""

from apps.auth.domain.exceptions.base import DomainError


class InvalidTokenError(DomainError):
    """유효하지 않은 토큰."""

    def __init__(self, reason: str = "Invalid token") -> None:
        super().__init__(reason)


class TokenExpiredError(DomainError):
    """만료된 토큰."""

    def __init__(self) -> None:
        super().__init__("Token has expired")


class TokenTypeMismatchError(DomainError):
    """토큰 타입 불일치."""

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(f"Token type mismatch: expected {expected}, got {actual}")


class TokenRevokedError(DomainError):
    """폐기된 토큰."""

    def __init__(self, jti: str | None = None) -> None:
        message = f"Token revoked: {jti}" if jti else "Token has been revoked"
        super().__init__(message)
