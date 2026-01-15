"""Prometheus Metrics - Chat Worker 모니터링.

메트릭 종류:
- Counter: 누적 카운트 (요청 수, 에러 수)
- Histogram: 분포 측정 (응답 시간)
- Gauge: 현재 값 (활성 작업 수)

라벨:
- intent: 의도 (waste, character, location, general)
- status: 상태 (success, error)
- provider: LLM 제공자 (openai, gemini)
"""

from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Callable, Generator

from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# ============================================================
# Service Info
# ============================================================

CHAT_WORKER_INFO = Info(
    "chat_worker",
    "Chat Worker service information",
)
CHAT_WORKER_INFO.info(
    {
        "version": "1.0.0",
        "framework": "langgraph",
    }
)

# ============================================================
# Request Metrics
# ============================================================

CHAT_REQUESTS_TOTAL = Counter(
    "chat_requests_total",
    "Total number of chat requests",
    ["intent", "status", "provider"],
)

CHAT_REQUEST_DURATION = Histogram(
    "chat_request_duration_seconds",
    "Chat request duration in seconds",
    ["intent", "provider"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

CHAT_ERRORS_TOTAL = Counter(
    "chat_errors_total",
    "Total number of chat errors",
    ["intent", "error_type"],
)

CHAT_ACTIVE_JOBS = Gauge(
    "chat_active_jobs",
    "Number of currently active chat jobs",
)

# ============================================================
# Intent Metrics
# ============================================================

CHAT_INTENT_DISTRIBUTION = Counter(
    "chat_intent_distribution_total",
    "Distribution of classified intents",
    ["intent"],
)

# ============================================================
# Vision Metrics
# ============================================================

CHAT_VISION_REQUESTS = Counter(
    "chat_vision_requests_total",
    "Total number of vision analysis requests",
    ["status", "provider"],
)

CHAT_VISION_DURATION = Histogram(
    "chat_vision_duration_seconds",
    "Vision analysis duration in seconds",
    ["provider"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
)

# ============================================================
# Subagent Metrics
# ============================================================

CHAT_SUBAGENT_CALLS = Counter(
    "chat_subagent_calls_total",
    "Total number of subagent calls",
    ["subagent", "status"],
)

CHAT_SUBAGENT_DURATION = Histogram(
    "chat_subagent_duration_seconds",
    "Subagent call duration in seconds",
    ["subagent"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# ============================================================
# Token Usage Metrics
# ============================================================

CHAT_TOKEN_USAGE = Counter(
    "chat_token_usage_total",
    "Total tokens used",
    ["provider", "type"],  # type: input, output
)

# ============================================================
# Helper Functions
# ============================================================


@contextmanager
def track_request(
    intent: str = "unknown",
    provider: str = "openai",
) -> Generator[None, None, None]:
    """요청 추적 컨텍스트 매니저.

    Usage:
        with track_request(intent="waste", provider="openai"):
            result = await pipeline.ainvoke(state)
    """
    CHAT_ACTIVE_JOBS.inc()
    start_time = time.perf_counter()
    status = "success"

    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start_time
        CHAT_ACTIVE_JOBS.dec()
        CHAT_REQUESTS_TOTAL.labels(
            intent=intent,
            status=status,
            provider=provider,
        ).inc()
        CHAT_REQUEST_DURATION.labels(
            intent=intent,
            provider=provider,
        ).observe(duration)


def track_intent(intent: str) -> None:
    """의도 분류 추적."""
    CHAT_INTENT_DISTRIBUTION.labels(intent=intent).inc()


def track_vision(
    status: str = "success",
    provider: str = "openai",
    duration: float | None = None,
) -> None:
    """Vision 분석 추적."""
    CHAT_VISION_REQUESTS.labels(status=status, provider=provider).inc()
    if duration is not None:
        CHAT_VISION_DURATION.labels(provider=provider).observe(duration)


def track_subagent(
    subagent: str,
    status: str = "success",
    duration: float | None = None,
) -> None:
    """Subagent 호출 추적."""
    CHAT_SUBAGENT_CALLS.labels(subagent=subagent, status=status).inc()
    if duration is not None:
        CHAT_SUBAGENT_DURATION.labels(subagent=subagent).observe(duration)


def track_tokens(
    provider: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """토큰 사용량 추적."""
    if input_tokens > 0:
        CHAT_TOKEN_USAGE.labels(provider=provider, type="input").inc(input_tokens)
    if output_tokens > 0:
        CHAT_TOKEN_USAGE.labels(provider=provider, type="output").inc(output_tokens)


def track_error(intent: str, error_type: str) -> None:
    """에러 추적."""
    CHAT_ERRORS_TOTAL.labels(intent=intent, error_type=error_type).inc()


# ============================================================
# Decorator
# ============================================================


def metrics_tracked(
    intent: str = "unknown",
    provider: str = "openai",
) -> Callable:
    """메트릭 추적 데코레이터.

    Usage:
        @metrics_tracked(intent="waste", provider="openai")
        async def process_waste_query(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with track_request(intent=intent, provider=provider):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
