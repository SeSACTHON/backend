"""LangSmith OpenTelemetry Integration.

LangSmith의 LangGraph 추적 데이터를 OpenTelemetry로 내보내
Jaeger에서 LLM 파이프라인 전체 흐름을 추적할 수 있게 합니다.

환경변수:
- LANGSMITH_TRACING=true: LangSmith 추적 활성화
- LANGSMITH_API_KEY: LangSmith API 키
- LANGSMITH_OTEL_ENABLED=true: OTEL 내보내기 활성화

통합 흐름:
  API Request → MQ Publish → Worker Consume → LangGraph Pipeline → LLM Calls
                    │                               │                  │
                    └── Jaeger ◄────────────────────┴──────────────────┘

참조:
- https://docs.langchain.com/langsmith/trace-with-opentelemetry
- langsmith[otel]>=0.4.25 필요
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Environment variables
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_OTEL_ENABLED = os.getenv("LANGSMITH_OTEL_ENABLED", "true").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "eco2-chat-worker")

# Global state
_otel_exporter = None
_is_configured = False


def configure_langsmith_otel() -> bool:
    """LangSmith OpenTelemetry 통합 설정.

    LangSmith 추적 데이터를 현재 TracerProvider로 내보냅니다.
    broker.py의 _setup_aio_pika_tracing()에서 TracerProvider가
    먼저 설정되어 있어야 합니다.

    Returns:
        bool: 설정 성공 여부
    """
    global _otel_exporter, _is_configured

    if _is_configured:
        return True

    if not LANGSMITH_TRACING:
        logger.info("LangSmith tracing disabled (LANGSMITH_TRACING=false)")
        return False

    if not LANGSMITH_API_KEY:
        logger.warning("LangSmith API key not set (LANGSMITH_API_KEY)")
        return False

    if not LANGSMITH_OTEL_ENABLED:
        logger.info("LangSmith OTEL export disabled (LANGSMITH_OTEL_ENABLED=false)")
        return False

    try:
        from langsmith import Client
        from langsmith.wrappers import OpenTelemetryTracer

        # LangSmith 클라이언트 초기화
        client = Client(api_key=LANGSMITH_API_KEY)

        # OpenTelemetry Tracer로 LangSmith 추적 래핑
        # 현재 TracerProvider를 사용하여 Jaeger로 내보냄
        _otel_exporter = OpenTelemetryTracer(client=client)

        _is_configured = True
        logger.info(
            "LangSmith OTEL integration enabled",
            extra={
                "project": LANGSMITH_PROJECT,
                "otel_export": True,
            },
        )
        return True

    except ImportError as e:
        logger.warning(
            f"LangSmith OTEL not available: {e}. "
            "Install: pip install 'langsmith[otel]>=0.4.25'"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to configure LangSmith OTEL: {e}")
        return False


def get_langsmith_run_config(
    job_id: str,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    """LangSmith + LangGraph run config 생성.

    LangGraph 실행 시 사용할 config를 생성합니다.
    - run_name: Jaeger/LangSmith에서 표시될 이름
    - tags: 필터링용 태그
    - metadata: 추가 컨텍스트

    Args:
        job_id: 작업 ID
        session_id: 세션 ID
        user_id: 사용자 ID

    Returns:
        LangGraph config dict
    """
    config: dict[str, Any] = {
        "run_name": f"chat-{job_id[:8]}",
        "tags": ["chat-worker", "langgraph"],
        "metadata": {
            "job_id": job_id,
            "session_id": session_id,
            "user_id": user_id,
        },
        "configurable": {},
    }

    # Multi-turn 대화용 thread_id 설정
    if session_id:
        config["configurable"]["thread_id"] = session_id

    return config


class TelemetryConfig:
    """Telemetry 설정 포트 구현.

    ProcessChatCommand에서 사용하는 TelemetryConfigPort 구현체.
    """

    def get_run_config(
        self,
        job_id: str,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """LangGraph run config 반환."""
        return get_langsmith_run_config(job_id, session_id, user_id)
