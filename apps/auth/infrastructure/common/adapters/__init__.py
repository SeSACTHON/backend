"""Common Adapters.

저장소 기술과 무관한 Port 구현체입니다.
"""

from auth.infrastructure.common.adapters.users_id_generator_uuid import (
    UuidUsersIdGenerator,
)

__all__ = ["UuidUsersIdGenerator"]
