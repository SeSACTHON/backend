"""Chat Service

폐기물 분류 및 분리배출 안내 챗봇 서비스
- 이미지 파이프라인: Vision API → RAG → Answer
- 텍스트 파이프라인: Text Classification → RAG → Answer
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Protocol

from domains._shared.schemas.waste import WasteClassificationResult
from domains._shared.waste_pipeline import process_waste_classification
from domains._shared.waste_pipeline.answer import generate_answer
from domains._shared.waste_pipeline.rag import get_disposal_rules
from domains._shared.waste_pipeline.text import classify_text
from domains.chat.core.constants import (
    FALLBACK_MESSAGE,
    PIPELINE_TYPE_IMAGE,
    PIPELINE_TYPE_TEXT,
)
from domains.chat.metrics import (
    increment_fallback,
    increment_request,
    observe_pipeline_duration,
)
from domains.chat.schemas.chat import ChatMessageRequest, ChatMessageResponse


logger = logging.getLogger(__name__)


# =============================================================================
# 예외 정의
# =============================================================================


class ChatServiceError(Exception):
    """Chat 서비스 기본 예외"""

    pass


class PipelineExecutionError(ChatServiceError):
    """파이프라인 실행 실패"""

    def __init__(self, pipeline_type: str, cause: Exception):
        self.pipeline_type = pipeline_type
        self.cause = cause
        super().__init__(f"{pipeline_type} pipeline failed: {cause}")


class ClassificationError(ChatServiceError):
    """분류 실패"""

    pass


class AnswerGenerationError(ChatServiceError):
    """답변 생성 실패"""

    pass


# =============================================================================
# 파이프라인 프로토콜 (의존성 주입용)
# =============================================================================


class ImagePipelineProtocol(Protocol):
    """이미지 파이프라인 인터페이스"""

    def __call__(
        self,
        user_input: str,
        image_url: str,
        *,
        save_result: bool,
        verbose: bool,
    ) -> dict: ...


class TextClassifierProtocol(Protocol):
    """텍스트 분류기 인터페이스"""

    def __call__(self, user_input: str, *, save_result: bool) -> dict: ...


# =============================================================================
# ChatService
# =============================================================================


class ChatService:
    """채팅 서비스

    폐기물 분류 및 분리배출 안내를 제공합니다.
    이미지 또는 텍스트 입력을 받아 적절한 파이프라인을 실행합니다.
    """

    def __init__(
        self,
        *,
        image_pipeline: ImagePipelineProtocol | None = None,
        text_classifier: TextClassifierProtocol | None = None,
    ) -> None:
        """ChatService 초기화

        Args:
            image_pipeline: 이미지 파이프라인 (테스트용 주입)
            text_classifier: 텍스트 분류기 (테스트용 주입)
        """
        self._image_pipeline = image_pipeline or process_waste_classification
        self._text_classifier = text_classifier or classify_text

    async def send_message(
        self,
        payload: ChatMessageRequest,
    ) -> ChatMessageResponse:
        """메시지 처리 및 응답 생성

        Args:
            payload: 채팅 요청 (메시지, 이미지 URL 등)

        Returns:
            ChatMessageResponse: 챗봇 응답
        """
        image_url = str(payload.image_url) if payload.image_url else None
        pipeline_type = PIPELINE_TYPE_IMAGE if image_url else PIPELINE_TYPE_TEXT

        logger.info(
            "Chat message received",
            extra={
                "pipeline_type": pipeline_type,
                "has_image": image_url is not None,
                "message_length": len(payload.message),
            },
        )

        timer_start = perf_counter()
        success = False

        try:
            pipeline_result = await self._run_pipeline(payload.message, image_url)
            success = True
            return ChatMessageResponse(
                user_answer=self._render_answer(pipeline_result, payload.message)
            )

        except PipelineExecutionError as exc:
            logger.error(
                "Pipeline execution failed",
                extra={
                    "pipeline_type": exc.pipeline_type,
                    "error_type": type(exc.cause).__name__,
                    "error_message": str(exc.cause),
                },
                exc_info=True,
            )
            increment_fallback()
            return ChatMessageResponse(user_answer=self._fallback_answer(payload.message))

        except Exception as exc:
            logger.exception(
                "Unexpected error in send_message",
                extra={"error_type": type(exc).__name__},
            )
            increment_fallback()
            return ChatMessageResponse(user_answer=self._fallback_answer(payload.message))

        finally:
            duration = perf_counter() - timer_start
            observe_pipeline_duration(pipeline_type, duration)
            increment_request(pipeline_type, success)

            logger.info(
                "Chat message processed",
                extra={
                    "pipeline_type": pipeline_type,
                    "duration_ms": duration * 1000,
                    "success": success,
                },
            )

    def _fallback_answer(self, message: str) -> str:
        """폴백 응답 반환

        Args:
            message: 원본 메시지 (현재 미사용, 향후 확장용)

        Returns:
            폴백 메시지
        """
        return FALLBACK_MESSAGE

    async def _run_pipeline(
        self,
        user_input: str,
        image_url: str | None,
    ) -> WasteClassificationResult:
        """적절한 파이프라인 실행

        Args:
            user_input: 사용자 입력 텍스트
            image_url: 이미지 URL (없으면 텍스트 파이프라인)

        Returns:
            WasteClassificationResult: 분류 결과

        Raises:
            PipelineExecutionError: 파이프라인 실행 실패
        """
        if image_url:
            return await self._run_image_pipeline(user_input, image_url)
        return await self._run_text_pipeline(user_input)

    async def _run_image_pipeline(
        self,
        user_input: str,
        image_url: str,
    ) -> WasteClassificationResult:
        """이미지 파이프라인 실행

        Args:
            user_input: 사용자 질문
            image_url: 이미지 URL

        Returns:
            WasteClassificationResult: 분류 결과

        Raises:
            PipelineExecutionError: 파이프라인 실행 실패
        """
        started_at = datetime.now(timezone.utc)
        logger.info(
            "Image pipeline started",
            extra={
                "started_at": started_at.isoformat(),
                "image_url": image_url,
            },
        )

        try:
            result = await asyncio.to_thread(
                self._image_pipeline,
                user_input,
                image_url,
                save_result=False,
                verbose=False,
            )
            return WasteClassificationResult(**result)

        except Exception as exc:
            raise PipelineExecutionError(PIPELINE_TYPE_IMAGE, exc) from exc

        finally:
            finished_at = datetime.now(timezone.utc)
            elapsed_ms = (finished_at - started_at).total_seconds() * 1000
            logger.info(
                "Image pipeline finished",
                extra={
                    "finished_at": finished_at.isoformat(),
                    "elapsed_ms": elapsed_ms,
                },
            )

    async def _run_text_pipeline(self, user_input: str) -> WasteClassificationResult:
        """텍스트 파이프라인 실행

        Args:
            user_input: 사용자 질문

        Returns:
            WasteClassificationResult: 분류 결과

        Raises:
            PipelineExecutionError: 파이프라인 실행 실패
        """
        started_at = datetime.now(timezone.utc)
        logger.info(
            "Text pipeline started",
            extra={"started_at": started_at.isoformat()},
        )

        try:
            result = await asyncio.to_thread(
                self._execute_text_pipeline,
                user_input,
            )
            return WasteClassificationResult(**result)

        except Exception as exc:
            raise PipelineExecutionError(PIPELINE_TYPE_TEXT, exc) from exc

        finally:
            finished_at = datetime.now(timezone.utc)
            elapsed_ms = (finished_at - started_at).total_seconds() * 1000
            logger.info(
                "Text pipeline finished",
                extra={
                    "finished_at": finished_at.isoformat(),
                    "elapsed_ms": elapsed_ms,
                },
            )

    def _execute_text_pipeline(self, user_input: str) -> dict:
        """텍스트 파이프라인 동기 실행

        Args:
            user_input: 사용자 질문

        Returns:
            파이프라인 결과 dict
        """
        classification_result = self._text_classifier(user_input, save_result=False)
        disposal_rules = get_disposal_rules(classification_result) or {}
        final_answer = generate_answer(
            classification_result,
            disposal_rules,
            save_result=False,
            pipeline_type=PIPELINE_TYPE_TEXT,
        )
        return {
            "classification_result": classification_result,
            "disposal_rules": disposal_rules,
            "final_answer": final_answer,
        }

    def _render_answer(
        self,
        pipeline_result: WasteClassificationResult,
        original_message: str,
    ) -> str:
        """파이프라인 결과에서 사용자 답변 추출

        Args:
            pipeline_result: 파이프라인 결과
            original_message: 원본 메시지 (폴백용)

        Returns:
            사용자에게 보여줄 답변
        """
        final_answer = pipeline_result.final_answer or {}
        text = str(final_answer.get("user_answer") or "").strip()

        if text:
            return text

        return self._fallback_answer(original_message)
