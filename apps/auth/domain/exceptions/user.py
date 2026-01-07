"""User Domain Exceptions."""

from auth.domain.exceptions.base import DomainError


class UserNotFoundError(DomainError):
    """사용자를 찾을 수 없음."""

    def __init__(self, user_id: str | None = None) -> None:
        message = f"User not found: {user_id}" if user_id else "User not found"
        super().__init__(message)


class UserAlreadyExistsError(DomainError):
    """사용자가 이미 존재함."""

    def __init__(self, identifier: str | None = None) -> None:
        message = f"User already exists: {identifier}" if identifier else "User already exists"
        super().__init__(message)
