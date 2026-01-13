"""Process Chat Command - 최상위 유스케이스 엔트리.

Application Layer의 핵심 진입점.
메인 유스케이스로서 서브 서비스들(intent, answer, integrations, interaction)을 조율.

호출 순서:
1. queued 이벤트 발행
2. 파이프라인 실행 (LangGraph)
   - Intent → Route → [RAG/Character/Location] → Answer
3. done 이벤트 발행
4. 결과 반환

상태 모델:
- queued: 작업 대기
- running: 파이프라인 실행 중
- waiting_human: Human-in-the-Loop 대기 (interaction)
- completed: 완료
- failed: 실패
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort

# Prometheus Metrics (lazy import to avoid import errors in tests)
try:
    from chat_worker.infrastructure.metrics import (
        track_request,
        track_intent,
        track_error,
    )

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

logger = logging.getLogger(__name__)


# ============================================================
# Pipeline Protocol (Graph 인터페이스)
# ============================================================


class ChatPipelinePort(Protocol):
    """Chat 파이프라인 Port.

    LangGraph 구현을 추상화.
    테스트 시 Mock으로 교체 가능.
    """

    async def ainvoke(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """파이프라인 실행."""
        ...


# ============================================================
# Request/Response DTOs
# ============================================================


@dataclass
class ProcessChatRequest:
    """Chat 처리 요청."""

    job_id: str
    session_id: str
    user_id: str
    message: str
    image_url: str | None = None
    user_location: dict[str, float] | None = None
    model: str | None = None


@dataclass
class ProcessChatResponse:
    """Chat 처리 응답."""

    job_id: str
    session_id: str
    status: str  # "completed" | "failed"
    intent: str | None
    answer: str | None
    error: str | None = None


# ============================================================
# Use Case (Main Entry Point)
# ============================================================


class ProcessChatCommand:
    """Chat 파이프라인 실행 Command.

    최상위 유스케이스로서:
    - 파이프라인 실행 조율 (LangGraph)
    - 시작/완료/실패 이벤트 발행 (ProgressNotifier)
    - 결과 포맷팅

    서브 서비스들:
    - intent/: IntentClassifier
    - answer/: AnswerGenerator
    - integrations/: CharacterService, LocationService
    - interaction/: HumanInputService

    ```
    ProcessChatCommand (여기)
          │
          └── ChatPipelinePort (LangGraph)
                    │
                    ├── IntentService
                    ├── AnswerService
                    ├── integrations/CharacterService
                    ├── integrations/LocationService
                    └── interaction/HumanInputService
    ```
    """

    def __init__(
        self,
        pipeline: ChatPipelinePort,
        progress_notifier: "ProgressNotifierPort",
    ):
        self._pipeline = pipeline
        self._progress_notifier = progress_notifier

    async def execute(self, request: ProcessChatRequest) -> ProcessChatResponse:
        """Chat 파이프라인 실행.

        상태 전이:
        queued → running → [waiting_human] → completed/failed
        """
        log_ctx = {
            "job_id": request.job_id,
            "session_id": request.session_id,
            "user_id": request.user_id,
        }
        logger.info("ProcessChatCommand started", extra=log_ctx)

        start_time = time.perf_counter()
        intent = "unknown"
        status = "success"

        try:
            # 1. 작업 시작 이벤트 (queued → running)
            await self._progress_notifier.notify_stage(
                task_id=request.job_id,
                stage="queued",
                status="started",
                progress=0,
                message="🚀 작업이 시작되었습니다...",
            )

            # 2. 파이프라인 실행
            initial_state = {
                "job_id": request.job_id,
                "session_id": request.session_id,
                "user_id": request.user_id,
                "message": request.message,
                "image_url": request.image_url,
                "user_location": request.user_location,
            }

            # 세션 ID → thread_id로 멀티턴 대화 컨텍스트 연결
            config = {
                "configurable": {
                    "thread_id": request.session_id,
                }
            }

            result = await self._pipeline.ainvoke(initial_state, config=config)

            intent = result.get("intent", "unknown")

            # Metrics: Intent 추적
            if METRICS_ENABLED:
                track_intent(intent)

            # 3. 작업 완료 이벤트 (running → completed)
            await self._progress_notifier.notify_stage(
                task_id=request.job_id,
                stage="done",
                status="completed",
                progress=100,
                result={
                    "intent": intent,
                    "answer": result.get("answer"),
                },
            )

            logger.info(
                "ProcessChatCommand completed",
                extra={**log_ctx, "intent": intent},
            )

            return ProcessChatResponse(
                job_id=request.job_id,
                session_id=request.session_id,
                status="completed",
                intent=intent,
                answer=result.get("answer"),
            )

        except Exception as e:
            status = "error"
            logger.error(
                "ProcessChatCommand failed",
                extra={**log_ctx, "error": str(e)},
                exc_info=True,
            )

            # Metrics: 에러 추적
            if METRICS_ENABLED:
                track_error(intent, type(e).__name__)

            # 작업 실패 이벤트 (running → failed)
            await self._progress_notifier.notify_stage(
                task_id=request.job_id,
                stage="done",
                status="failed",
                result={"error": str(e)},
            )

            return ProcessChatResponse(
                job_id=request.job_id,
                session_id=request.session_id,
                status="failed",
                intent=None,
                answer=None,
                error=str(e),
            )

        finally:
            # Metrics: 요청 시간 추적
            duration = time.perf_counter() - start_time
            if METRICS_ENABLED:
                from chat_worker.infrastructure.metrics import (
                    CHAT_REQUESTS_TOTAL,
                    CHAT_REQUEST_DURATION,
                )

                CHAT_REQUESTS_TOTAL.labels(
                    intent=intent,
                    status=status,
                    provider="openai",  # TODO: 실제 provider 추적
                ).inc()
                CHAT_REQUEST_DURATION.labels(
                    intent=intent,
                    provider="openai",
                ).observe(duration)
