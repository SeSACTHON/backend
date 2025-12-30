"""UUID User ID Generator.

UserIdGenerator 포트의 구현체입니다.
"""

import uuid

from apps.auth.domain.value_objects.user_id import UserId


class UuidUserIdGenerator:
    """UUID v4 기반 사용자 ID 생성기.

    UserIdGenerator 구현체.
    """

    def __call__(self) -> UserId:
        """새 UserId 생성."""
        return UserId(value=uuid.uuid4())
