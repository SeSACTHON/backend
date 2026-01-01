"""Auth Application Exceptions."""

from apps.auth.application.common.exceptions.base import ApplicationError


class AuthenticationError(ApplicationError):
    """인증 실패."""

    def __init__(self, reason: str = "Authentication failed") -> None:
        super().__init__(reason)


class InvalidStateError(ApplicationError):
    """OAuth 상태 검증 실패."""

    def __init__(self, reason: str = "Invalid or expired state") -> None:
        super().__init__(reason)


class OAuthProviderError(ApplicationError):
    """OAuth 프로바이더 오류."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        super().__init__(f"OAuth provider error ({provider}): {reason}")


class UserServiceUnavailableError(ApplicationError):
    """Users 서비스 통신 실패.

    gRPC 통신 오류, Circuit Breaker 열림 등으로 인해
    users 도메인과 통신할 수 없는 경우 발생합니다.
    """

    def __init__(self, reason: str = "Users service unavailable") -> None:
        super().__init__(reason)
