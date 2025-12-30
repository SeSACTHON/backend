"""Domain Ports (Interfaces).

도메인 레이어에서 필요로 하는 외부 기능의 인터페이스입니다.
구현체는 Infrastructure 레이어에 있습니다.
"""

from apps.auth.domain.ports.user_id_generator import UserIdGenerator

__all__ = ["UserIdGenerator"]
