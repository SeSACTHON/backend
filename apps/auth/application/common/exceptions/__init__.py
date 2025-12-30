"""Application Exceptions."""

from apps.auth.application.common.exceptions.base import ApplicationError
from apps.auth.application.common.exceptions.auth import (
    AuthenticationError,
    InvalidStateError,
    OAuthProviderError,
)
from apps.auth.application.common.exceptions.gateway import (
    GatewayError,
    DataMapperError,
)

__all__ = [
    "ApplicationError",
    "AuthenticationError",
    "InvalidStateError",
    "OAuthProviderError",
    "GatewayError",
    "DataMapperError",
]
