"""Redis Token Blacklist.

TokenBlacklist 포트의 구현체입니다.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from apps.auth.domain.value_objects.token_payload import TokenPayload

if TYPE_CHECKING:
    import redis.asyncio as aioredis

BLACKLIST_KEY_PREFIX = "blacklist:jti:"


class RedisTokenBlacklist:
    """Redis 기반 토큰 블랙리스트.

    TokenBlacklist 구현체.
    """

    def __init__(self, redis: "aioredis.Redis") -> None:
        self._redis = redis

    async def add(self, payload: TokenPayload, reason: str = "revoked") -> None:
        """토큰을 블랙리스트에 추가."""
        key = f"{BLACKLIST_KEY_PREFIX}{payload.jti}"
        # 토큰 만료 시간까지만 유지
        ttl = max(payload.exp - int(time.time()), 1)
        await self._redis.setex(key, ttl, reason)

    async def contains(self, jti: str) -> bool:
        """토큰이 블랙리스트에 있는지 확인."""
        key = f"{BLACKLIST_KEY_PREFIX}{jti}"
        return await self._redis.exists(key) > 0
