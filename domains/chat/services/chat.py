from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    AsyncOpenAI = None  # type: ignore

from domains._shared.schemas.waste import WasteClassificationResult
from domains._shared.waste_pipeline import PipelineError, process_waste_classification
from domains.chat.schemas.chat import ChatMessageRequest, ChatMessageResponse


logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.1"


class ChatService:
    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_CHAT_MODEL", DEFAULT_MODEL)
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key) if AsyncOpenAI and api_key else None

    async def send_message(
        self,
        payload: ChatMessageRequest,
    ) -> ChatMessageResponse:
        image_url = str(payload.image_url) if payload.image_url else None

        if image_url:
            try:
                pipeline_result = await self._run_image_pipeline(payload.message, image_url)
            except PipelineError:
                logger.exception("Image pipeline failed; falling back to text response.")
            else:
                message_text = (
                    pipeline_result.final_answer.get("user_answer")
                    or pipeline_result.final_answer.get("answer")
                    or self._fallback_answer(payload.message)
                )
                return ChatMessageResponse(user_answer=message_text)

        if not self.client:
            fallback = self._fallback_answer(payload.message)
            logger.warning("ChatService fallback: OpenAI client missing.")
            return ChatMessageResponse(user_answer=fallback)

        openai_input = self._build_messages(payload.message)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "OpenAI request payload: %s",
                json.dumps(openai_input, ensure_ascii=False),
            )

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=openai_input,
                temperature=payload.temperature,
            )
            content = response.output[0].content[0].text  # type: ignore[index]
            logger.debug("OpenAI response success (model=%s)", self.model)
        except Exception:  # pragma: no cover - network errors
            logger.exception("OpenAI responses.create failed; using fallback answer.")
            content = self._fallback_answer(payload.message)

        return ChatMessageResponse(user_answer=content)

    def _build_messages(self, current: str) -> list[dict]:
        def _to_message(role: str, text: str) -> dict:
            content_type = "output_text" if role == "assistant" else "input_text"
            return {
                "role": role,
                "content": [
                    {
                        "type": content_type,
                        "text": text,
                    }
                ],
            }

        system_text = (
            "You are EcoMate, an assistant that answers recycling and sustainability "
            "questions in Korean. Provide concise, practical answers."
        )
        return [
            _to_message("system", system_text),
            _to_message("user", current),
        ]

    def _fallback_answer(self, message: str) -> str:
        return (
            "모델 연결이 설정되지 않아 기본 답변을 제공합니다. "
            "질문: {question} → 페트병은 세척 후 라벨과 뚜껑을 분리하여 배출해주세요."
        ).format(question=message)

    async def _run_image_pipeline(
        self,
        user_input: str,
        image_url: str,
    ) -> WasteClassificationResult:
        started_at = datetime.now(timezone.utc)
        logger.info(
            "Chat image pipeline started at %s (image_url=%s)",
            started_at.isoformat(),
            image_url,
        )
        success = False
        try:
            result = await asyncio.to_thread(
                process_waste_classification,
                user_input,
                image_url,
                save_result=False,
                verbose=False,
            )
            success = True
            return WasteClassificationResult(**result)
        finally:
            finished_at = datetime.now(timezone.utc)
            elapsed_ms = (finished_at - started_at).total_seconds() * 1000
            logger.info(
                "Chat image pipeline finished at %s (%.1f ms, success=%s)",
                finished_at.isoformat(),
                elapsed_ms,
                success,
            )
