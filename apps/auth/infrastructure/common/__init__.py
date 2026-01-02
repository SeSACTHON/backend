"""Common Infrastructure.

저장소 기술과 무관한 공통 구현체입니다.
"""

from apps.auth.infrastructure.common.adapters import UuidUsersIdGenerator

__all__ = ["UuidUsersIdGenerator"]
