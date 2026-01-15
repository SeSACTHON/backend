"""Aggregator Node - 병렬 실행 결과 수집.

Send API로 병렬 실행된 노드들의 결과를 수집하고
answer_node로 전달할 최종 state를 준비합니다.

LangGraph의 Send API 특성:
- 여러 Send가 병렬 실행되면 각 결과가 state에 병합됨
- 이 노드는 병합된 결과를 검증/로깅하고 answer로 전달

역할:
1. 병렬 실행 결과 존재 여부 확인
2. 누락된 컨텍스트 로깅 (디버깅용)
3. answer_node를 위한 최종 state 정리
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort

logger = logging.getLogger(__name__)


def create_aggregator_node(
    event_publisher: "ProgressNotifierPort",
):
    """결과 수집 노드 팩토리.

    Args:
        event_publisher: 이벤트 발행자 (SSE)

    Returns:
        aggregator_node 함수
    """

    async def aggregator_node(state: dict[str, Any]) -> dict[str, Any]:
        """병렬 실행 결과 수집 및 정리.

        LangGraph Send API가 병렬 실행 후 자동 병합한 state를 받아서:
        1. 어떤 컨텍스트가 수집되었는지 로깅
        2. 누락된 필드 기본값 설정
        3. answer_node를 위한 최종 state 반환

        Args:
            state: 병렬 실행 후 병합된 상태

        Returns:
            정리된 상태
        """
        job_id = state.get("job_id", "")

        # Progress: 집계 시작
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="aggregate",
            status="started",
            progress=60,
            message="📊 정보 취합 중...",
        )

        # 수집된 컨텍스트 필드들
        context_fields = {
            "disposal_rules": "RAG 검색 결과",
            "character_context": "캐릭터 정보",
            "location_context": "장소 정보",
            "web_search_results": "웹 검색 결과",
            "bulk_waste_context": "대형폐기물 정보",
            "recyclable_price_context": "재활용 시세",
            "weather_context": "날씨 정보",
            "collection_point_context": "수거함 위치",
            "image_generation_context": "이미지 생성",
        }

        # 수집된 컨텍스트 확인
        collected = []
        missing = []

        for field, description in context_fields.items():
            value = state.get(field)
            if value is not None:
                # dict인 경우 success 필드 확인
                if isinstance(value, dict):
                    if value.get("success", True):  # success 없으면 True로 간주
                        collected.append(description)
                    else:
                        missing.append(f"{description} (실패)")
                else:
                    collected.append(description)
            else:
                # None인 것은 해당 노드가 실행되지 않았거나 결과 없음
                pass  # 의도적으로 실행 안 된 것은 로깅 안 함

        logger.info(
            "Aggregator: contexts collected",
            extra={
                "job_id": job_id,
                "collected_count": len(collected),
                "collected": collected,
            },
        )

        if missing:
            logger.warning(
                "Aggregator: some contexts failed",
                extra={
                    "job_id": job_id,
                    "failed": missing,
                },
            )

        # Progress: 집계 완료
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="aggregate",
            status="completed",
            progress=65,
            result={"collected": collected},
        )

        # state 그대로 반환 (병합은 이미 LangGraph가 처리)
        return state

    return aggregator_node


__all__ = ["create_aggregator_node"]
