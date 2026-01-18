"""OpenTelemetry Tracing Middleware for Taskiq.

Taskiq 메시지에서 W3C TraceContext를 추출하여
분산 트레이싱을 연결합니다.

API → MQ → Worker 간 trace context 전파:
1. Chat API가 traceparent를 메시지 labels에 주입
2. 이 미들웨어가 labels에서 traceparent 추출
3. 추출된 context를 parent로 하는 새 span 생성
4. Jaeger에서 전체 요청 흐름 추적 가능

사용법:
    broker.add_middlewares(TracingMiddleware())
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from taskiq import TaskiqMiddleware, TaskiqMessage, TaskiqResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"


class TracingMiddleware(TaskiqMiddleware):
    """Taskiq OpenTelemetry 트레이싱 미들웨어.

    메시지 labels에서 W3C TraceContext 추출하여
    분산 트레이싱을 연결합니다.
    """

    def __init__(self):
        """초기화."""
        self._tracer = None

    def _get_tracer(self):
        """Tracer lazy 초기화."""
        if self._tracer is None and OTEL_ENABLED:
            try:
                from opentelemetry import trace

                self._tracer = trace.get_tracer("chat-worker.taskiq")
            except ImportError:
                pass
        return self._tracer

    def _extract_context(self, labels: dict[str, str]):
        """메시지 labels에서 trace context 추출.

        Args:
            labels: Taskiq 메시지 labels (traceparent, tracestate 포함)

        Returns:
            OpenTelemetry Context 또는 None
        """
        if not OTEL_ENABLED:
            return None

        traceparent = labels.get("traceparent")
        if not traceparent:
            return None

        try:
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            propagator = TraceContextTextMapPropagator()
            ctx = propagator.extract(carrier=labels)

            logger.debug(
                "Trace context extracted from message",
                extra={"traceparent": traceparent},
            )
            return ctx

        except Exception as e:
            logger.warning(f"Failed to extract trace context: {e}")
            return None

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """태스크 실행 전 trace context 설정.

        메시지 labels에서 traceparent 추출하여
        OpenTelemetry context에 설정합니다.
        """
        if not OTEL_ENABLED:
            return message

        labels = message.labels or {}
        ctx = self._extract_context(labels)

        if ctx is not None:
            try:
                from opentelemetry import context as otel_context

                # 추출된 context를 현재 context로 설정
                token = otel_context.attach(ctx)
                # token을 labels에 저장 (post_execute에서 detach용)
                message.labels["_otel_token"] = str(id(token))
                # 실제 token 객체를 인스턴스 변수에 저장
                if not hasattr(self, "_tokens"):
                    self._tokens = {}
                self._tokens[message.task_id] = token

                logger.debug(
                    "Trace context attached",
                    extra={
                        "task_id": message.task_id,
                        "task_name": message.task_name,
                        "traceparent": labels.get("traceparent"),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to attach trace context: {e}")

        return message

    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        """태스크 실행 후 context 정리.

        pre_execute에서 attach한 context를 detach합니다.
        """
        if not OTEL_ENABLED:
            return

        if hasattr(self, "_tokens") and message.task_id in self._tokens:
            try:
                from opentelemetry import context as otel_context

                token = self._tokens.pop(message.task_id)
                otel_context.detach(token)

                logger.debug(
                    "Trace context detached",
                    extra={"task_id": message.task_id},
                )
            except Exception as e:
                logger.warning(f"Failed to detach trace context: {e}")
