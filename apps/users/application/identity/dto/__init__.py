"""Identity DTO."""

from users.application.identity.dto.oauth import (
    OAuthUserRequest,
    OAuthUserResult,
    UpdateLoginTimeRequest,
)

__all__ = [
    "OAuthUserRequest",
    "OAuthUserResult",
    "UpdateLoginTimeRequest",
]
