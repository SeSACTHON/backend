"""Redis Cache Layer.

캐릭터 카탈로그 등 자주 조회되는 데이터를 캐싱합니다.

Cache Strategy:
    - Cache-aside pattern (Lazy loading)
    - TTL 기반 만료 (default: 5분)
    - Graceful degradation (Redis 실패 시 DB 직접 조회)

Usage:
    from domains.character.core.cache import get_cached, set_cached, invalidate_cache

    # 조회
    data = await get_cached("character:catalog")

    # 저장
    await set_cached("character:catalog", catalog_data, ttl=300)

    # 무효화
    await invalidate_cache("character:catalog")
"""

from __future__ import annotations

import json
import logging
from typing import Any

from domains.character.core.config import get_settings

logger = logging.getLogger(__name__)

# Lazy-loaded Redis client
_redis_client = None

# Cache key prefixes
CACHE_PREFIX = "character:"
CATALOG_KEY = f"{CACHE_PREFIX}catalog"


async def _get_redis():
    """Lazy initialization of Redis client."""
    global _redis_client

    settings = get_settings()
    if not settings.cache_enabled:
        return None

    if _redis_client is None:
        try:
            import redis.asyncio as redis

            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Connection test
            await _redis_client.ping()
            logger.info(
                "Redis cache connected",
                extra={"url": settings.redis_url.split("@")[-1]},  # 비밀번호 제거
            )
        except Exception as e:
            logger.warning(
                "Redis cache unavailable, falling back to no-cache",
                extra={"error": str(e)},
            )
            _redis_client = None

    return _redis_client


async def get_cached(key: str) -> Any | None:
    """캐시에서 값 조회.

    Args:
        key: 캐시 키

    Returns:
        캐시된 값 또는 None (미스 또는 에러)
    """
    try:
        redis = await _get_redis()
        if redis is None:
            return None

        data = await redis.get(key)
        if data is not None:
            logger.debug("Cache hit", extra={"key": key})
            return json.loads(data)

        logger.debug("Cache miss", extra={"key": key})
        return None

    except Exception as e:
        logger.warning("Cache get error", extra={"key": key, "error": str(e)})
        return None


async def set_cached(key: str, value: Any, ttl: int | None = None) -> bool:
    """캐시에 값 저장.

    Args:
        key: 캐시 키
        value: 저장할 값 (JSON 직렬화 가능해야 함)
        ttl: TTL 초 (None이면 설정의 기본값 사용)

    Returns:
        저장 성공 여부
    """
    try:
        redis = await _get_redis()
        if redis is None:
            return False

        settings = get_settings()
        ttl = ttl or settings.cache_ttl_seconds

        await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        logger.debug("Cache set", extra={"key": key, "ttl": ttl})
        return True

    except Exception as e:
        logger.warning("Cache set error", extra={"key": key, "error": str(e)})
        return False


async def invalidate_cache(key: str) -> bool:
    """캐시 무효화.

    Args:
        key: 캐시 키

    Returns:
        삭제 성공 여부
    """
    try:
        redis = await _get_redis()
        if redis is None:
            return False

        await redis.delete(key)
        logger.info("Cache invalidated", extra={"key": key})
        return True

    except Exception as e:
        logger.warning("Cache invalidate error", extra={"key": key, "error": str(e)})
        return False


async def invalidate_catalog_cache() -> bool:
    """카탈로그 캐시 무효화 (헬퍼 함수)."""
    return await invalidate_cache(CATALOG_KEY)


async def close_cache() -> None:
    """Redis 연결 종료 (graceful shutdown)."""
    global _redis_client

    if _redis_client is not None:
        try:
            await _redis_client.aclose()
            logger.info("Redis cache connection closed")
        except Exception as e:
            logger.warning("Error closing Redis connection", extra={"error": str(e)})
        finally:
            _redis_client = None


def reset_cache_client() -> None:
    """캐시 클라이언트 리셋 (테스트용).

    테스트 간 상태 격리를 위해 글로벌 클라이언트를 초기화합니다.
    프로덕션 코드에서는 사용하지 마세요.

    Usage:
        @pytest.fixture(autouse=True)
        def reset_cache():
            reset_cache_client()
            yield
            reset_cache_client()
    """
    global _redis_client
    _redis_client = None


def set_cache_client(client) -> None:
    """캐시 클라이언트 주입 (테스트용).

    테스트에서 mock Redis 클라이언트를 주입할 때 사용합니다.

    Args:
        client: Redis 클라이언트 또는 Mock 객체
    """
    global _redis_client
    _redis_client = client
