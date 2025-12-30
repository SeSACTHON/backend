"""Application DTOs (Data Transfer Objects)."""

from apps.auth.application.common.dto.auth import (
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    LogoutRequest,
    RefreshTokensRequest,
    RefreshTokensResponse,
)

__all__ = [
    "OAuthAuthorizeRequest",
    "OAuthAuthorizeResponse",
    "OAuthCallbackRequest",
    "OAuthCallbackResponse",
    "LogoutRequest",
    "RefreshTokensRequest",
    "RefreshTokensResponse",
]
