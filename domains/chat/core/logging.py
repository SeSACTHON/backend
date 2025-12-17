"""
Structured Logging Configuration (ECS-based)

Elastic Common Schema (ECS) 기반 JSON 로깅 설정
OpenTelemetry trace_id 자동 연동

Log Collection Protocol:
- Fluent Bit → Elasticsearch: HTTP (9200)
- OpenTelemetry → Jaeger: gRPC OTLP (4317)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from domains.chat.core.config import SERVICE_NAME, SERVICE_VERSION

try:
    from opentelemetry import trace

    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False


class ECSJsonFormatter(logging.Formatter):
    """
    Elastic Common Schema (ECS) 기반 JSON 포매터

    출력 예시:
    {
        "@timestamp": "2025-12-17T10:00:00.000Z",
        "message": "Chat session started",
        "log.level": "info",
        "log.logger": "domains.chat.services.chat",
        "service.name": "chat-api",
        "service.version": "1.0.7",
        "service.environment": "dev",
        "trace.id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span.id": "00f067aa0ba902b7"
    }
    """

    def __init__(
        self,
        service_name: str = SERVICE_NAME,
        service_version: str = SERVICE_VERSION,
        environment: str = "dev",
    ):
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        # 기본 ECS 필드
        log_obj: dict[str, Any] = {
            "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "message": record.getMessage(),
            "log.level": record.levelname.lower(),
            "log.logger": record.name,
            "ecs.version": "8.11.0",
            "service.name": self.service_name,
            "service.version": self.service_version,
            "service.environment": self.environment,
        }

        # OpenTelemetry trace context 추가
        if HAS_OPENTELEMETRY:
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_obj["trace.id"] = format(ctx.trace_id, "032x")
                log_obj["span.id"] = format(ctx.span_id, "016x")

        # 에러 정보 추가
        if record.exc_info:
            log_obj["error.type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            log_obj["error.message"] = str(record.exc_info[1]) if record.exc_info[1] else None
            log_obj["error.stack_trace"] = self.formatException(record.exc_info)

        # extra 필드 추가 (labels로 그룹화)
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
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
            }:
                extra_fields[key] = value

        if extra_fields:
            log_obj["labels"] = extra_fields

        return json.dumps(log_obj, ensure_ascii=False, default=str)


def configure_logging(
    service_name: str = SERVICE_NAME,
    service_version: str = SERVICE_VERSION,
    log_level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """
    애플리케이션 로깅 설정

    Args:
        service_name: 서비스 이름
        service_version: 서비스 버전
        log_level: 로그 레벨 (환경변수 LOG_LEVEL로 오버라이드 가능)
        json_format: JSON 포맷 사용 여부 (환경변수 LOG_FORMAT=json으로 오버라이드)
    """
    # 환경변수에서 설정 읽기
    environment = os.getenv("ENVIRONMENT", "dev")
    level = log_level or os.getenv("LOG_LEVEL", "INFO")
    use_json = json_format if json_format is not None else os.getenv("LOG_FORMAT", "json") == "json"

    # 로그 레벨 설정
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 새 핸들러 추가
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    if use_json:
        handler.setFormatter(
            ECSJsonFormatter(
                service_name=service_name,
                service_version=service_version,
                environment=environment,
            )
        )
    else:
        # 개발 환경: 가독성 좋은 포맷
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
