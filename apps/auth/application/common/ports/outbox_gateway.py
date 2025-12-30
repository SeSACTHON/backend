"""OutboxGateway Port.

Outbox 패턴을 위한 Gateway 인터페이스입니다.
"""

from typing import Protocol


class OutboxGateway(Protocol):
    """Outbox 저장소 인터페이스.

    구현체:
        - RedisOutbox (infrastructure/persistence_redis/)
    """

    def push(self, key: str, data: str) -> bool:
        """이벤트를 Outbox에 추가.

        Args:
            key: 큐 키
            data: JSON 직렬화된 이벤트 데이터

        Returns:
            성공 여부
        """
        ...

    def pop(self, key: str) -> str | None:
        """Outbox에서 이벤트 꺼내기.

        Args:
            key: 큐 키

        Returns:
            이벤트 데이터 또는 None
        """
        ...

    def length(self, key: str) -> int:
        """Outbox 큐 길이 조회.

        Args:
            key: 큐 키

        Returns:
            큐 길이
        """
        ...
