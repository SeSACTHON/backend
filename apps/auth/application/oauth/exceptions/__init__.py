"""OAuth domain exceptions."""

from auth.application.oauth.exceptions.oauth import (
    InvalidStateError,
    OAuthProviderError,
)

__all__ = [
    "InvalidStateError",
    "OAuthProviderError",
]
