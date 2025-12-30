"""Redis Outbox.

OutboxGateway 포트의 구현체입니다.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)


class RedisOutbox:
    """Redis 기반 Outbox.

    OutboxGateway 구현체.
    FIFO 큐로 동작: LPUSH로 추가, RPOP으로 제거
    """

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    def push(self, key: str, data: str) -> bool:
        """이벤트를 Outbox에 추가."""
        try:
            self._redis.lpush(key, data)
            logger.debug(f"Pushed to outbox: key={key}")
            return True
        except Exception as e:
            logger.exception(f"Failed to push to outbox: {e}")
            return False

    def pop(self, key: str) -> str | None:
        """Outbox에서 이벤트 꺼내기."""
        try:
            result = self._redis.rpop(key)
            if result is None:
                return None
            return result.decode("utf-8") if isinstance(result, bytes) else result
        except Exception as e:
            logger.exception(f"Failed to pop from outbox: {e}")
            return None

    def length(self, key: str) -> int:
        """Outbox 큐 길이 조회."""
        try:
            return self._redis.llen(key)
        except Exception as e:
            logger.exception(f"Failed to get outbox length: {e}")
            return 0
