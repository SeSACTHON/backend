"""Domain Exceptions."""

from auth.domain.exceptions.auth import (
    InvalidTokenError,
    TokenExpiredError,
    TokenTypeMismatchError,
)
from auth.domain.exceptions.base import DomainError
from auth.domain.exceptions.user import UserAlreadyExistsError, UserNotFoundError
from auth.domain.exceptions.validation import InvalidEmailError, ValidationError

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
