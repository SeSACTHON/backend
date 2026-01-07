"""Domain Services.

도메인 비즈니스 로직을 담당합니다.
엔티티 단독으로 처리하기 어려운 로직을 서비스로 분리합니다.
"""

from auth.domain.services.user_service import UserService

__all__ = ["UserService"]
