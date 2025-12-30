"""Validation Domain Exceptions."""

from apps.auth.domain.exceptions.base import DomainError


class ValidationError(DomainError):
    """값 검증 실패."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Validation error for '{field}': {reason}")


class InvalidEmailError(DomainError):
    """유효하지 않은 이메일."""

    def __init__(self, reason: str = "Invalid email format") -> None:
        super().__init__(reason)
