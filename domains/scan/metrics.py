"""Scan 도메인 Prometheus 메트릭

ext-authz 메트릭 구조 참고:
- 세분화된 Histogram buckets (ExponentialBucketsRange 유사)
- 명확한 label 구조 (result, reason, status)
- Gauge/Counter/Histogram 목적별 분리
"""

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)
METRICS_PATH = "/metrics/status"

# ─────────────────────────────────────────────────────────────────────────────
# Bucket 설정 (ext-authz ExponentialBucketsRange 참고)
# - 낮은 latency에 더 세분화된 bucket
# - tail latency 탐지를 위한 상위 bucket
# ─────────────────────────────────────────────────────────────────────────────

# TTFB: 첫 이벤트까지 시간 (10ms ~ 5s, 12 buckets)
TTFB_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

# Stage Duration: 각 스테이지 소요 시간 (100ms ~ 30s, 15 buckets)
STAGE_BUCKETS = (0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0)

# Chain Duration: 전체 파이프라인 (1s ~ 120s, 15 buckets)
CHAIN_BUCKETS = (
    1.0,
    2.0,
    3.0,
    5.0,
    7.5,
    10.0,
    12.5,
    15.0,
    20.0,
    25.0,
    30.0,
    45.0,
    60.0,
    90.0,
    120.0,
)

# Celery Task: 개별 태스크 (10ms ~ 30s, 15 buckets)
CELERY_TASK_BUCKETS = (
    0.01,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    3.0,
    5.0,
    7.5,
    10.0,
    15.0,
    20.0,
    25.0,
    30.0,
)


def register_metrics(app: FastAPI) -> None:
    """Prometheus /metrics 엔드포인트 등록"""

    @app.get(METRICS_PATH, include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


# ─────────────────────────────────────────────────────────────────────────────
# SSE Completion 엔드포인트 메트릭
# ─────────────────────────────────────────────────────────────────────────────

SSE_CONNECTIONS_ACTIVE = Gauge(
    "scan_sse_connections_active",
    "Number of active SSE connections",
    registry=REGISTRY,
)

SSE_CHAIN_DURATION = Histogram(
    "scan_sse_chain_duration_seconds",
    "Total duration of SSE chain (vision → rule → answer → reward)",
    registry=REGISTRY,
    buckets=CHAIN_BUCKETS,
)

SSE_STAGE_DURATION = Histogram(
    "scan_sse_stage_duration_seconds",
    "Duration of each SSE stage",
    labelnames=["stage"],  # vision, rule, answer, reward
    registry=REGISTRY,
    buckets=STAGE_BUCKETS,
)

SSE_REQUESTS_TOTAL = Counter(
    "scan_sse_requests_total",
    "Total SSE requests by status",
    labelnames=["status"],  # success, failed, timeout
    registry=REGISTRY,
)

SSE_TTFB = Histogram(
    "scan_sse_ttfb_seconds",
    "Time to first byte (first SSE event)",
    registry=REGISTRY,
    buckets=TTFB_BUCKETS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Celery Task 메트릭
# ─────────────────────────────────────────────────────────────────────────────

CELERY_TASK_DURATION = Histogram(
    "scan_celery_task_duration_seconds",
    "Duration of Celery task execution",
    labelnames=["task_name", "status"],  # success, failed, retry
    registry=REGISTRY,
    buckets=CELERY_TASK_BUCKETS,
)

CELERY_TASK_TOTAL = Counter(
    "scan_celery_task_total",
    "Total Celery task executions",
    labelnames=["task_name", "status"],  # success, failed, retry
    registry=REGISTRY,
)

CELERY_QUEUE_SIZE = Gauge(
    "scan_celery_queue_size",
    "Number of messages in Celery queue",
    labelnames=["queue"],
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────────────────────
# Scan 도메인 커스텀 비즈니스 메트릭
# ─────────────────────────────────────────────────────────────────────────────

PIPELINE_STEP_LATENCY = Histogram(
    "scan_pipeline_step_duration_seconds",
    "Duration of each step in the waste classification pipeline",
    labelnames=["step"],
    registry=REGISTRY,
    buckets=(
        0.1,
        0.5,
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
        7.0,
        8.0,
        9.0,
        10.0,
        12.5,
        15.0,
        20.0,
    ),
)

REWARD_MATCH_LATENCY = Histogram(
    "scan_reward_match_duration_seconds",
    "Duration of character reward matching API call",
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REWARD_MATCH_COUNTER = Counter(
    "scan_reward_match_total",
    "Total count of character reward matching attempts",
    labelnames=["status"],  # success, failed, skipped
    registry=REGISTRY,
)

GRPC_CALL_LATENCY = Histogram(
    "scan_grpc_call_duration_seconds",
    "Duration of gRPC calls to external services",
    labelnames=["service", "method"],
    registry=REGISTRY,
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

GRPC_CALL_COUNTER = Counter(
    "scan_grpc_call_total",
    "Total count of gRPC calls",
    labelnames=["service", "method", "status"],
    registry=REGISTRY,
)
