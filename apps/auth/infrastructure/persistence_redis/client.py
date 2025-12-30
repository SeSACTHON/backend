"""Redis Client Provider.

기존 domains/auth/infrastructure/redis/client.py와 호환.
블랙리스트용과 OAuth 상태용 클라이언트를 분리합니다.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis


def _build_async_client(redis_url: str) -> "aioredis.Redis":
    """비동기 Redis 클라이언트 생성."""
    import redis.asyncio as aioredis

    return aioredis.from_url(redis_url, decode_responses=True)


@lru_cache
def get_blacklist_redis() -> "aioredis.Redis":
    """토큰 블랙리스트용 Redis 클라이언트.

    환경변수:
        - AUTH_REDIS_BLACKLIST_URL (default: redis://localhost:6379/0)
    """
    from apps.auth.setup.config import get_settings

    settings = get_settings()
    return _build_async_client(settings.redis_blacklist_url)


@lru_cache
def get_oauth_state_redis() -> "aioredis.Redis":
    """OAuth 상태 저장용 Redis 클라이언트.

    환경변수:
        - AUTH_REDIS_OAUTH_STATE_URL (default: redis://localhost:6379/3)
    """
    from apps.auth.setup.config import get_settings

    settings = get_settings()
    return _build_async_client(settings.redis_oauth_state_url)
