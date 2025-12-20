"""
Structured Logging Configuration (ECS-based)

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

from domains.chat.core.constants import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    ECS_VERSION,
    ENV_KEY_ENVIRONMENT,
    ENV_KEY_LOG_FORMAT,
    ENV_KEY_LOG_LEVEL,
    EXCLUDED_LOG_RECORD_ATTRS,
    MASK_MIN_LENGTH,
    MASK_PLACEHOLDER,
    MASK_PRESERVE_PREFIX,
    MASK_PRESERVE_SUFFIX,
    NOISY_LOGGERS,
    SENSITIVE_FIELD_PATTERNS,
    SERVICE_NAME,
    SERVICE_VERSION,
)

try:
    from opentelemetry import trace

    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False


# =============================================================================
# PII 마스킹 함수
# =============================================================================


def _is_sensitive_key(key: str) -> bool:
    """Check if a key matches sensitive field patterns."""
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SENSITIVE_FIELD_PATTERNS)


def _mask_value(value: Any) -> str:
    """Mask a sensitive value with partial visibility."""
    if value is None:
        return MASK_PLACEHOLDER
    str_value = str(value)
    if len(str_value) <= MASK_MIN_LENGTH:
        return MASK_PLACEHOLDER
    return f"{str_value[:MASK_PRESERVE_PREFIX]}...{str_value[-MASK_PRESERVE_SUFFIX:]}"


def _mask_list_items(items: list) -> list:
    """리스트 내 dict 항목들을 마스킹."""
    return [mask_sensitive_data(item) if isinstance(item, dict) else item for item in items]


def _mask_dict_value(key: str, value: Any) -> Any:
    """단일 key-value 쌍 마스킹 처리."""
    if _is_sensitive_key(key):
        return _mask_value(value)
    if isinstance(value, dict):
        return mask_sensitive_data(value)
    if isinstance(value, list):
        return _mask_list_items(value)
    return value


def mask_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask sensitive fields in a dictionary."""
    if not isinstance(data, dict):
        return data
    return {key: _mask_dict_value(key, value) for key, value in data.items()}


# =============================================================================
# ECS JSON 포매터
# =============================================================================


def _get_trace_context() -> dict[str, str]:
    """OpenTelemetry trace context 추출."""
    if not HAS_OPENTELEMETRY:
        return {}

    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return {}

    return {
        "trace.id": format(ctx.trace_id, "032x"),
        "span.id": format(ctx.span_id, "016x"),
    }


def _get_error_context(record: logging.LogRecord) -> dict[str, Any]:
    """로그 레코드에서 에러 정보 추출."""
    if not record.exc_info:
        return {}

    exc_type, exc_value, _ = record.exc_info
    return {
        "error.type": exc_type.__name__ if exc_type else None,
        "error.message": str(exc_value) if exc_value else None,
        "error.stack_trace": logging.Formatter().formatException(record.exc_info),
    }


def _get_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """로그 레코드에서 extra 필드 추출."""
    extra = {
        key: value for key, value in record.__dict__.items() if key not in EXCLUDED_LOG_RECORD_ATTRS
    }
    return {"labels": mask_sensitive_data(extra)} if extra else {}


class ECSJsonFormatter(logging.Formatter):
    """Elastic Common Schema (ECS) 기반 JSON 포매터."""

    def __init__(
        self,
        service_name: str = SERVICE_NAME,
        service_version: str = SERVICE_VERSION,
        environment: str = DEFAULT_ENVIRONMENT,
    ):
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment

    def _build_base_log(self, record: logging.LogRecord) -> dict[str, Any]:
        """기본 로그 객체 생성."""
        return {
            "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "message": record.getMessage(),
            "log.level": record.levelname.lower(),
            "log.logger": record.name,
            "ecs.version": ECS_VERSION,
            "service.name": self.service_name,
            "service.version": self.service_version,
            "service.environment": self.environment,
        }

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 ECS JSON 형식으로 변환."""
        log_obj = self._build_base_log(record)
        log_obj.update(_get_trace_context())
        log_obj.update(_get_error_context(record))
        log_obj.update(_get_extra_fields(record))

        return json.dumps(log_obj, ensure_ascii=False, default=str)


# =============================================================================
# 로깅 설정
# =============================================================================


def _create_json_formatter(
    service_name: str,
    service_version: str,
    environment: str,
) -> logging.Formatter:
    """JSON 포매터 생성."""
    return ECSJsonFormatter(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
    )


def _create_text_formatter() -> logging.Formatter:
    """텍스트 포매터 생성."""
    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _suppress_noisy_loggers() -> None:
    """노이즈가 많은 라이브러리 로거 레벨 조정."""
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def configure_logging(
    service_name: str = SERVICE_NAME,
    service_version: str = SERVICE_VERSION,
    log_level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """애플리케이션 로깅 설정.

    Args:
        service_name: 서비스 이름
        service_version: 서비스 버전
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        json_format: JSON 포맷 사용 여부
    """
    environment = os.getenv(ENV_KEY_ENVIRONMENT, DEFAULT_ENVIRONMENT)
    level = log_level or os.getenv(ENV_KEY_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    use_json = (
        json_format
        if json_format is not None
        else os.getenv(ENV_KEY_LOG_FORMAT, DEFAULT_LOG_FORMAT) == "json"
    )

    numeric_level = getattr(logging, level.upper(), logging.DEBUG)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 새 핸들러 설정
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = (
        _create_json_formatter(service_name, service_version, environment)
        if use_json
        else _create_text_formatter()
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # 노이즈 로거 억제
    _suppress_noisy_loggers()
