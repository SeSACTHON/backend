"""Chat 도메인 Prometheus 메트릭

수집 항목:
- 파이프라인 처리 시간 (image/text별)
- 요청 성공/실패 카운터
- 파이프라인 타입별 요청 수
"""

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

from domains.chat.core.constants import (
    METRIC_FALLBACK_TOTAL,
    METRIC_PIPELINE_DURATION,
    METRIC_REQUESTS_TOTAL,
    METRICS_PATH,
    PIPELINE_DURATION_BUCKETS,
    STATUS_ERROR,
    STATUS_SUCCESS,
)

REGISTRY = CollectorRegistry(auto_describe=True)

# =============================================================================
# Histogram: 파이프라인 처리 시간
# =============================================================================

PIPELINE_DURATION = Histogram(
    name=METRIC_PIPELINE_DURATION,
    documentation="Time spent processing chat pipeline",
    labelnames=["pipeline_type"],  # "image" or "text"
    buckets=PIPELINE_DURATION_BUCKETS,
    registry=REGISTRY,
)

# =============================================================================
# Counter: 요청 결과
# =============================================================================

REQUEST_TOTAL = Counter(
    name=METRIC_REQUESTS_TOTAL,
    documentation="Total number of chat requests",
    labelnames=["pipeline_type", "status"],  # status: "success" or "error"
    registry=REGISTRY,
)

# =============================================================================
# Counter: 폴백 응답 수
# =============================================================================

FALLBACK_TOTAL = Counter(
    name=METRIC_FALLBACK_TOTAL,
    documentation="Total number of fallback responses returned",
    registry=REGISTRY,
)


# =============================================================================
# 메트릭 헬퍼 함수
# =============================================================================


def observe_pipeline_duration(pipeline_type: str, duration_seconds: float) -> None:
    """파이프라인 처리 시간 기록

    Args:
        pipeline_type: "image" 또는 "text"
        duration_seconds: 처리 시간 (초)
    """
    PIPELINE_DURATION.labels(pipeline_type=pipeline_type).observe(duration_seconds)


def increment_request(pipeline_type: str, success: bool) -> None:
    """요청 카운터 증가

    Args:
        pipeline_type: "image" 또는 "text"
        success: 성공 여부
    """
    status = STATUS_SUCCESS if success else STATUS_ERROR
    REQUEST_TOTAL.labels(pipeline_type=pipeline_type, status=status).inc()


def increment_fallback() -> None:
    """폴백 응답 카운터 증가"""
    FALLBACK_TOTAL.inc()


# =============================================================================
# FastAPI 엔드포인트 등록
# =============================================================================


def register_metrics(app: FastAPI) -> None:
    """Prometheus /metrics 엔드포인트 등록"""

    @app.get(METRICS_PATH, include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
