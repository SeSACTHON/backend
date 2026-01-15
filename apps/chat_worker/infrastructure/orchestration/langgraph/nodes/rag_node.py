"""RAG Node - LangGraph 어댑터.

얇은 어댑터: state 변환 + Command 호출 + progress notify (UX).
정책/흐름은 SearchRAGCommand(Application)에서 처리.

Clean Architecture:
- Node(Adapter): 이 파일 - LangGraph glue code
- Command(UseCase): SearchRAGCommand - 정책/흐름
- Service: RAGSearcherService - 순수 비즈니스 로직
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chat_worker.application.commands import (
    SearchRAGCommand,
    SearchRAGInput,
)

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort
    from chat_worker.application.ports.retrieval import RetrieverPort

logger = logging.getLogger(__name__)


def create_rag_node(
    retriever: "RetrieverPort",
    event_publisher: "ProgressNotifierPort",
):
    """RAG 노드 팩토리.

    Node는 LangGraph 어댑터:
    - state → input DTO 변환
    - Command(UseCase) 호출
    - output → state 변환
    - progress notify (UX)

    Args:
        retriever: 검색 Port
        event_publisher: 진행률 이벤트 발행자 (UX)

    Returns:
        rag_node 함수
    """
    # Command(UseCase) 인스턴스 생성 - Port 조립
    command = SearchRAGCommand(retriever=retriever)

    async def rag_node(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드 (얇은 어댑터).

        역할:
        1. state에서 값 추출 (LangGraph glue)
        2. Command 호출 (정책/흐름 위임)
        3. output → state 변환

        Args:
            state: 현재 LangGraph 상태

        Returns:
            업데이트된 상태
        """
        job_id = state["job_id"]

        # Progress: 시작 (UX)
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="rag",
            status="started",
            progress=40,
            message="📚 규정 검색 중...",
        )

        try:
            # 1. state → input DTO 변환
            input_dto = SearchRAGInput(
                job_id=job_id,
                message=state.get("message", ""),
                classification=state.get("classification_result"),
            )

            # 2. Command 실행 (정책/흐름은 Command에서)
            output = await command.execute(input_dto)

            # 3. output → state 변환
            state_update = {
                **state,
                "disposal_rules": output.disposal_rules,
            }

            # Progress: 완료 (UX)
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="rag",
                status="completed",
                progress=60,
                result={
                    "found": output.found,
                    "method": output.search_method,
                },
            )

            return state_update

        except Exception as e:
            logger.error(f"RAG node failed: {e}", extra={"job_id": job_id})
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="rag",
                status="failed",
                result={"error": str(e)},
            )
            return {**state, "disposal_rules": None}

    return rag_node
