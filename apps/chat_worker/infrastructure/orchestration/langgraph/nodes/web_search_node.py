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
from chat_worker.infrastructure.orchestration.langgraph.context_helper import (
    create_context,
    create_error_context,
)
from chat_worker.infrastructure.orchestration.langgraph.nodes.node_executor import (
    NodeExecutor,
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

    Production Architecture:
    - NodeExecutor로 Policy 적용 (timeout, retry, circuit breaker)
    - web_search 노드는 FAIL_OPEN (보조 정보, 없어도 답변 가능)

    Channel Separation:
    - 출력 채널: web_search_results
    - Reducer: priority_preemptive_reducer
    - spread 금지: {"web_search_results": create_context(...)} 형태로 반환

    Args:
        web_search_client: 웹 검색 클라이언트 (DuckDuckGo/Tavily)
        event_publisher: 이벤트 발행기

    Returns:
        web_search_node 함수
    """
    # Command(UseCase) 인스턴스 생성 - Port 조립
    command = SearchWebCommand(web_search_client=web_search_client)

    async def _web_search_node_inner(state: dict[str, Any]) -> dict[str, Any]:
        """실제 노드 로직 (NodeExecutor가 래핑).

        역할:
        1. state에서 값 추출 (LangGraph glue)
        2. Command 호출 (정책/흐름 위임)
        3. output → state 변환
        4. progress notify (UX)

        Args:
            state: 현재 LangGraph 상태

        Returns:
            업데이트된 상태
        """
        job_id = state.get("job_id", "")

        # Progress: 시작 (UX)
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="web_search",
            status="started",
            progress=40,
            message="웹 검색 중",
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
                "web_search_results": create_error_context(
                    producer="web_search",
                    job_id=job_id,
                    error=output.error_message or "웹 검색 실패",
                ),
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
            message=f"웹 검색 완료: {results_count}건",
        )

        return {
            "web_search_results": create_context(
                data={
                    **(output.web_search_results or {}),
                    "search_query": output.search_query,
                },
                producer="web_search",
                job_id=job_id,
            ),
        }

    # NodeExecutor로 래핑 (Policy 적용: timeout, retry, circuit breaker)
    executor = NodeExecutor.get_instance()

    async def web_search_node(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드 (Policy 적용됨).

        NodeExecutor가 다음을 처리:
        - Circuit Breaker 확인
        - Timeout 적용 (10000ms)
        - Retry (1회)
        - FAIL_OPEN 처리 (실패해도 진행)
        """
        return await executor.execute(
            node_name="web_search",
            node_func=_web_search_node_inner,
            state=state,
        )

    return web_search_node
