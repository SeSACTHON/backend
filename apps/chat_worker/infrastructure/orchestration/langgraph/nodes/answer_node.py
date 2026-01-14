"""Answer Generation Node - 오케스트레이션 전용.

노드 책임: 이벤트 발행 + 서비스 호출 + state 업데이트
비즈니스 로직: AnswerGeneratorService에 위임

Prompt Strategy: Hybrid (Global + Local)
- Global: 이코 캐릭터 정의 (모든 Intent에 공통)
- Local: Intent별 지침 (waste/character/location/general)

References:
- docs/plans/chat-worker-prompt-strategy-adr.md
- docs/foundations/24-multi-agent-prompt-patterns.md
- arxiv:2504.20355 (Local Prompt Optimization)

Clean Architecture:
- Node: 오케스트레이션 (이 파일)
- Service: AnswerGeneratorService (비즈니스 로직)
- Port: LLMPort (순수 LLM 호출)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chat_worker.application.answer.dto import AnswerContext
from chat_worker.application.answer.services import AnswerGeneratorService
from chat_worker.infrastructure.orchestration.prompts import PromptBuilder

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort
    from chat_worker.application.ports.llm import LLMClientPort

logger = logging.getLogger(__name__)


def create_answer_node(
    llm: "LLMClientPort",
    event_publisher: "ProgressNotifierPort",
):
    """답변 생성 노드 팩토리.

    노드는 thin wrapper로:
    1. Intent에 따른 동적 프롬프트 생성 (Hybrid Pattern)
    2. 이벤트 발행
    3. AnswerGeneratorService 호출
    4. state 업데이트

    Prompt Strategy:
    - Global: 이코 캐릭터 정의 (모든 Intent에 공통)
    - Local: Intent별 지침 (waste/character/location/general)
    """
    # 서비스 인스턴스 (비즈니스 로직 담당)
    answer_service = AnswerGeneratorService(llm)

    # 프롬프트 빌더 (하이브리드 프롬프트)
    prompt_builder = PromptBuilder()

    async def answer_node(state: dict[str, Any]) -> dict[str, Any]:
        job_id = state["job_id"]
        message = state.get("message", "")
        intent = state.get("intent", "general")  # Intent 추출
        classification = state.get("classification_result")
        disposal_rules = state.get("disposal_rules")
        character_context = state.get("character_context")
        location_context = state.get("location_context")

        # 1. 이벤트: 시작
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="answer",
            status="started",
            progress=70,
            message="💭 답변 고민 중...",
        )

        try:
            # 2. Intent 기반 동적 프롬프트 생성 (Hybrid Pattern)
            system_prompt = prompt_builder.build(intent)
            logger.debug(f"Built prompt for intent={intent}, length={len(system_prompt)}")

            # 3. 컨텍스트 구성 (Service의 팩토리 메서드 사용)
            context = AnswerContext(
                classification=classification,
                disposal_rules=disposal_rules.get("data") if disposal_rules else None,
                character_context=character_context,
                location_context=location_context,
                user_input=message,
            )

            # 4. 서비스 호출 (스트리밍)
            answer_parts = []
            async for token in answer_service.generate_stream(
                context=context,
                system_prompt=system_prompt,  # 동적 프롬프트 적용
            ):
                # 토큰 이벤트 발행 (SSE 스트리밍)
                await event_publisher.notify_token(
                    task_id=job_id,
                    content=token,
                )
                answer_parts.append(token)

            answer = "".join(answer_parts)

            logger.info(
                "Answer generated",
                extra={
                    "job_id": job_id,
                    "length": len(answer),
                },
            )

            # 4. 이벤트: 완료
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="answer",
                status="completed",
                progress=100,
            )

            return {**state, "answer": answer}

        except Exception as e:
            logger.error(
                "Answer generation failed",
                extra={"job_id": job_id, "error": str(e)},
            )
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="answer",
                status="failed",
                result={"error": str(e)},
            )
            return {
                **state,
                "answer": "죄송해요, 답변 생성 중 오류가 발생했어요. 다시 시도해주세요! 🙏",
            }

    return answer_node
