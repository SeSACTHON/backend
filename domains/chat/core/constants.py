"""
Service Constants (Single Source of Truth)

정적 상수 정의 - 빌드 타임에 결정되며 환경변수로 변경되지 않음
"""

from __future__ import annotations

import math
from typing import Sequence

# =============================================================================
# Service Identity
# =============================================================================

SERVICE_NAME = "chat-api"
SERVICE_VERSION = "1.0.7"

# =============================================================================
# Logging Constants (12-Factor App Compliance)
# =============================================================================

ENV_KEY_ENVIRONMENT = "ENVIRONMENT"
ENV_KEY_LOG_LEVEL = "LOG_LEVEL"
ENV_KEY_LOG_FORMAT = "LOG_FORMAT"

DEFAULT_ENVIRONMENT = "dev"
DEFAULT_LOG_LEVEL = "DEBUG"
DEFAULT_LOG_FORMAT = "json"

ECS_VERSION = "8.11.0"

# 로그 레코드에서 제외할 기본 속성
EXCLUDED_LOG_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "message",
    }
)

# 노이즈가 많은 로거 목록 (레벨 조정 대상)
NOISY_LOGGERS = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "httpx",
    "httpcore",
    "asyncio",
)

# =============================================================================
# PII Masking Configuration (OWASP compliant)
# =============================================================================

SENSITIVE_FIELD_PATTERNS = frozenset({"password", "secret", "token", "api_key", "authorization"})
MASK_PLACEHOLDER = "***REDACTED***"
MASK_PRESERVE_PREFIX = 4
MASK_PRESERVE_SUFFIX = 4
MASK_MIN_LENGTH = 10

# =============================================================================
# Chat Service Constants
# =============================================================================

# 폴백 메시지
FALLBACK_MESSAGE = "이미지가 인식되지 않았어요! 다시 시도해주세요."

# 파이프라인 타입
PIPELINE_TYPE_IMAGE = "image"
PIPELINE_TYPE_TEXT = "text"

# =============================================================================
# API Constants
# =============================================================================

# 메시지 길이 제한
MESSAGE_MIN_LENGTH = 1
MESSAGE_MAX_LENGTH = 1000

# =============================================================================
# Metrics Constants
# =============================================================================

METRICS_PATH = "/metrics/status"

# 메트릭 이름
METRIC_PIPELINE_DURATION = "chat_pipeline_duration_seconds"
METRIC_REQUESTS_TOTAL = "chat_requests_total"
METRIC_FALLBACK_TOTAL = "chat_fallback_total"

# 메트릭 상태 레이블
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"


# -----------------------------------------------------------------------------
# Histogram Bucket Generators (Go Prometheus 스타일)
# Reference: https://pkg.go.dev/github.com/prometheus/client_golang/prometheus
# -----------------------------------------------------------------------------


def linear_buckets(start: float, width: float, count: int) -> tuple[float, ...]:
    """선형 간격 버킷 생성 (Go prometheus.LinearBuckets 호환).

    Args:
        start: 첫 번째 버킷 상한값
        width: 버킷 간 간격
        count: 버킷 개수

    Returns:
        버킷 상한값 튜플

    Raises:
        ValueError: count < 1

    Example:
        >>> linear_buckets(1.0, 0.5, 5)
        (1.0, 1.5, 2.0, 2.5, 3.0)
    """
    if count < 1:
        raise ValueError("linear_buckets: count must be positive")
    return tuple(round(start + i * width, 6) for i in range(count))


def exponential_buckets(start: float, factor: float, count: int) -> tuple[float, ...]:
    """지수 간격 버킷 생성 (Go prometheus.ExponentialBuckets 호환).

    Args:
        start: 첫 번째 버킷 상한값 (> 0)
        factor: 증가 배율 (> 1)
        count: 버킷 개수

    Returns:
        버킷 상한값 튜플

    Raises:
        ValueError: 잘못된 파라미터

    Example:
        >>> exponential_buckets(0.1, 2, 5)
        (0.1, 0.2, 0.4, 0.8, 1.6)
    """
    if count < 1:
        raise ValueError("exponential_buckets: count must be positive")
    if start <= 0:
        raise ValueError("exponential_buckets: start must be positive")
    if factor <= 1:
        raise ValueError("exponential_buckets: factor must be greater than 1")
    return tuple(round(start * (factor**i), 6) for i in range(count))


def exponential_buckets_range(
    min_val: float,
    max_val: float,
    count: int,
) -> tuple[float, ...]:
    """범위 기반 지수 버킷 생성 (Go prometheus.ExponentialBucketsRange 호환).

    min_val에서 max_val까지 count개의 지수 간격 버킷 생성.

    Args:
        min_val: 최소값 (> 0)
        max_val: 최대값 (> min_val)
        count: 버킷 개수 (>= 1)

    Returns:
        버킷 상한값 튜플

    Raises:
        ValueError: 잘못된 파라미터

    Example:
        >>> exponential_buckets_range(0.1, 10.0, 5)
        (0.1, 0.316..., 1.0, 3.16..., 10.0)
    """
    if count < 1:
        raise ValueError("exponential_buckets_range: count must be positive")
    if min_val <= 0:
        raise ValueError("exponential_buckets_range: min must be positive")
    if max_val <= min_val:
        raise ValueError("exponential_buckets_range: max must be greater than min")

    # factor = (max/min)^(1/(count-1))
    factor = math.pow(max_val / min_val, 1.0 / (count - 1)) if count > 1 else 1.0
    return exponential_buckets(min_val, factor, count)


def merge_buckets(*bucket_sets: Sequence[float]) -> tuple[float, ...]:
    """여러 버킷 세트를 병합 (중복 제거, 정렬).

    Args:
        *bucket_sets: 병합할 버킷 세트들

    Returns:
        정렬된 고유 버킷 튜플

    Example:
        >>> merge_buckets((0.1, 0.5, 1.0), (0.5, 2.0, 5.0))
        (0.1, 0.5, 1.0, 2.0, 5.0)
    """
    merged = set()
    for buckets in bucket_sets:
        merged.update(buckets)
    return tuple(sorted(merged))


# -----------------------------------------------------------------------------
# 용도별 버킷 세트 (scan 도메인 표준 기반)
# -----------------------------------------------------------------------------
# 버킷 값은 "nice round numbers" 원칙 적용
# - 사람이 읽기 쉬운 값: 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10 ...
# - 지수 스케일: 10^n 또는 2^n 기반
# - Grafana/Prometheus 대시보드에서 가독성 확보


def _nice_exponential_buckets(
    start: float,
    factor: float,
    count: int,
    precision: int = 2,
) -> tuple[float, ...]:
    """예쁜 숫자로 반올림된 지수 버킷 생성."""
    buckets = []
    current = start
    for _ in range(count):
        # 유효숫자 precision자리로 반올림
        rounded = round(current, precision)
        buckets.append(rounded)
        current *= factor
    return tuple(buckets)


# gRPC, 캐시 조회 등 빠른 작업용 (10ms ~ 2.5s)
# scan.GRPC_CALL_LATENCY 기반: (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
BUCKETS_FAST: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)

# API 호출, 보상 매칭 등 중간 작업용 (50ms ~ 5s)
# scan.REWARD_MATCH_LATENCY 기반: (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
BUCKETS_MEDIUM: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

# AI 파이프라인 처리용 (100ms ~ 20s)
# 구간별 최적화:
# - 빠른 구간 (0.1 ~ 1초): 지수 스케일 (factor=2)
# - 중간 구간 (1 ~ 10초): 선형 스케일 (1초 간격)
# - 느린 구간 (10 ~ 20초): 적응형 간격
BUCKETS_PIPELINE: tuple[float, ...] = merge_buckets(
    _nice_exponential_buckets(start=0.1, factor=2, count=4),  # 0.1, 0.2, 0.4, 0.8
    linear_buckets(start=1.0, width=1.0, count=10),  # 1, 2, ..., 10
    (12.5, 15.0, 20.0),  # 느린 구간
)

# 타임아웃 근처까지 확장 (100ms ~ 60s)
BUCKETS_EXTENDED: tuple[float, ...] = merge_buckets(
    BUCKETS_PIPELINE,
    (25.0, 30.0, 45.0, 60.0),  # 타임아웃 구간
)

# Chat 파이프라인용 기본 버킷
PIPELINE_DURATION_BUCKETS: tuple[float, ...] = BUCKETS_EXTENDED
