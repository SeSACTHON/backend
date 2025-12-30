"""UserIdGenerator Port.

사용자 ID 생성을 위한 도메인 포트입니다.
"""

from typing import Protocol

from apps.auth.domain.value_objects.user_id import UserId


class UserIdGenerator(Protocol):
    """사용자 ID 생성기 인터페이스.

    구현체:
        - UuidUserIdGenerator: UUID v4 기반 생성 (infrastructure/adapters/)
    """

    def __call__(self) -> UserId:
        """새 UserId 생성.

        Returns:
            생성된 UserId
        """
        ...
