"""Vision Node - LangGraph 어댑터.

얇은 어댑터: state 변환 + Command 호출 + progress notify (UX).
정책/흐름은 AnalyzeImageCommand(Application)에서 처리.

Clean Architecture:
- Node(Adapter): 이 파일 - LangGraph glue code
- Command(UseCase): AnalyzeImageCommand - 정책/흐름
- Service: VisionService - 순수 비즈니스 로직
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chat_worker.application.commands.analyze_image_command import (
    AnalyzeImageCommand,
    AnalyzeImageInput,
)

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort
    from chat_worker.application.ports.vision import VisionModelPort

logger = logging.getLogger(__name__)


def create_vision_node(
    vision_model: "VisionModelPort",
    event_publisher: "ProgressNotifierPort",
):
    """Vision 노드 생성.

    Node는 LangGraph 어댑터:
    - state → input DTO 변환
    - Command(UseCase) 호출
    - output → state 변환
    - progress notify (UX)

    Args:
        vision_model: Vision 모델 클라이언트
        event_publisher: 이벤트 발행자 (SSE)

    Returns:
        LangGraph 노드 함수
    """
    # Command(UseCase) 인스턴스 생성 - Port 조립
    command = AnalyzeImageCommand(vision_model=vision_model)

    async def vision_node(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드 (얇은 어댑터).

        역할:
        1. state에서 값 추출 (LangGraph glue)
        2. Command 호출 (정책/흐름 위임)
        3. output → state 변환

        Args:
            state: 현재 상태

        Returns:
            업데이트된 상태
        """
        job_id = state.get("job_id", "")
        image_url = state.get("image_url")

        # 이미지 없으면 빠른 스킵 (Progress 없이)
        if not image_url:
            logger.debug("No image_url, skipping vision node (job=%s)", job_id)
            return state

        # Progress: 시작 (UX)
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="vision",
            status="processing",
            progress=15,
            message="🔍 이미지 분석 중...",
        )

        # 1. state → input DTO 변환
        input_dto = AnalyzeImageInput(
            job_id=job_id,
            image_url=image_url,
            message=state.get("message", ""),
        )

        # 2. Command 실행 (정책/흐름은 Command에서)
        output = await command.execute(input_dto)

        # 3. output → state 변환
        if output.skipped:
            # 이미지 없어서 스킵됨 (이 케이스는 위에서 처리되지만 안전장치)
            return state

        if not output.success:
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="vision",
                status="failed",
                result={"error": output.error_message},
                message="⚠️ 이미지 분석 실패",
            )
            return {
                **state,
                "classification_result": output.classification_result,
                "has_image": output.has_image,
                "vision_error": output.error_message,
            }

        # Progress: 완료 (UX)
        major_category = (
            output.classification_result.get("classification", {}).get("major", "unknown")
            if output.classification_result
            else "unknown"
        )
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="vision",
            status="completed",
            progress=25,
            result={"major_category": major_category},
            message=f"✅ 분류 완료: {major_category}",
        )

        return {
            **state,
            "classification_result": output.classification_result,
            "has_image": output.has_image,
        }

    return vision_node
