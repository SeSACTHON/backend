from __future__ import annotations

import logging

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from domains.image.core.config import get_settings

logger = logging.getLogger(__name__)

# Redis connection pool health check interval (seconds)
# Prevents "Connection closed by server" errors from idle connections
HEALTH_CHECK_INTERVAL = 30

# Retry configuration
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.1  # 100ms base delay

_redis_client: Redis | None = None


def get_upload_redis() -> Redis:
    """Get Redis client with retry and connection pool settings.

    Retry policy:
    - ExponentialBackoff: 100ms → 200ms → 400ms
    - Max 3 retries on connection errors
    - Auto-reconnect on connection failures
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()

        # Retry with exponential backoff
        retry = Retry(
            backoff=ExponentialBackoff(base=RETRY_BASE_DELAY),
            retries=RETRY_ATTEMPTS,
        )

        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=HEALTH_CHECK_INTERVAL,
            retry=retry,
            retry_on_timeout=True,
            retry_on_error=[
                redis.ConnectionError,
                redis.TimeoutError,
                ConnectionResetError,
                ConnectionError,
            ],
            socket_keepalive=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info(
            "Redis client initialized",
            extra={
                "health_check_interval": HEALTH_CHECK_INTERVAL,
                "retry_attempts": RETRY_ATTEMPTS,
            },
        )
    return _redis_client


async def close_upload_redis() -> None:
    """Close Redis connection gracefully."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")
