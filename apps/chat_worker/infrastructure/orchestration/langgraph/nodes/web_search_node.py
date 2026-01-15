"""Web Search Node - LangGraph 어댑터.

얇은 어댑터: state 변환 + Command 호출 + progress notify (UX).
정책/흐름은 SearchWebCommand(Application)에서 처리.

Clean Architecture:
- Node(Adapter): 이 파일 - LangGraph glue code
- Command(UseCase): SearchWebCommand - 정책/흐름
- Service: WebSearchService - 순수 비즈니스 로직

사용 시나리오:
1. RAG에 없는 최신 분리배출 정책
2. 환경 관련 최신 뉴스/트렌드
3. 일반 상식 보완

Flow:
    Router → web_search → Answer
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chat_worker.application.commands.search_web_command import (
    SearchWebCommand,
    SearchWebInput,
)

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort
    from chat_worker.application.ports.web_search import WebSearchPort

logger = logging.getLogger(__name__)


def create_web_search_node(
    web_search_client: "WebSearchPort",
    event_publisher: "ProgressNotifierPort",
):
    """웹 검색 노드 팩토리.

    Node는 LangGraph 어댑터:
    - state → input DTO 변환
    - Command(UseCase) 호출
    - output → state 변환
    - progress notify (UX)

    Args:
        web_search_client: 웹 검색 클라이언트 (DuckDuckGo/Tavily)
        event_publisher: 이벤트 발행기

    Returns:
        web_search_node 함수
    """
    # Command(UseCase) 인스턴스 생성 - Port 조립
    command = SearchWebCommand(web_search_client=web_search_client)

    async def web_search_node(state: dict[str, Any]) -> dict[str, Any]:
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
            stage="web_search",
            status="started",
            progress=40,
            message="🔍 웹에서 최신 정보를 검색 중...",
        )

        # 1. state → input DTO 변환
        input_dto = SearchWebInput(
            job_id=job_id,
            message=state.get("message", ""),
            intent=state.get("intent", "general"),
            max_results=5,
            region="kr-kr",
        )

        # 2. Command 실행 (정책/흐름은 Command에서)
        output = await command.execute(input_dto)

        # 3. output → state 변환
        if not output.success:
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="web_search",
                status="failed",
                result={"error": output.error_message},
            )
            return {
                **state,
                "web_search_results": output.web_search_results,
                "web_search_error": output.error_message,
            }

        # Progress: 완료 (UX)
        results_count = (
            output.web_search_results.get("web_search", {}).get("count", 0)
            if output.web_search_results
            else 0
        )
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="web_search",
            status="completed",
            progress=50,
            result={
                "query": output.search_query,
                "results_count": results_count,
            },
        )

        return {
            **state,
            "web_search_results": output.web_search_results,
            "web_search_query": output.search_query,
        }

    return web_search_node
