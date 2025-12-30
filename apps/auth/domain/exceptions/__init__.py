"""Domain Exceptions."""

from apps.auth.domain.exceptions.base import DomainError
from apps.auth.domain.exceptions.user import UserNotFoundError, UserAlreadyExistsError
from apps.auth.domain.exceptions.auth import (
    InvalidTokenError,
    TokenExpiredError,
    TokenTypeMismatchError,
)
from apps.auth.domain.exceptions.validation import InvalidEmailError, ValidationError

__all__ = [
    "DomainError",
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "InvalidTokenError",
    "TokenExpiredError",
    "TokenTypeMismatchError",
    "InvalidEmailError",
    "ValidationError",
]
