"""Location Subagent Node - Orchestration Only.

LangGraph 파이프라인의 위치 검색 노드입니다.

노드 책임: 이벤트 발행 + 서비스 호출 + state 업데이트
비즈니스 로직: LocationService에 위임

Clean Architecture:
- Node: Orchestration만 담당 (이 파일)
- Service: LocationService (gRPC로 검색 + 컨텍스트 변환)
- Port: LocationClientPort (gRPC API 호출)

흐름:
1. 진행 이벤트 발행
2. 위치 확인 (state에서 user_location)
3. 위치 없으면 → needs_input 이벤트 발행 (HITL via HTTP)
4. 위치 있으면 → LocationService로 주변 센터 검색 (gRPC)
5. state 업데이트

HITL 흐름 (HTTP 기반):
1. Worker: needs_input 이벤트 발행 → SSE로 클라이언트 전달
2. Client: 위치 수집 (Geolocation API)
3. Client: POST /chat/{job_id}/input → HTTP로 위치 전송
4. Client: 새 요청 또는 재시도로 검색 수행
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from chat_worker.application.integrations.location.services import LocationService
from chat_worker.domain import LocationData

if TYPE_CHECKING:
    from chat_worker.application.integrations.location.ports import LocationClientPort
    from chat_worker.application.ports.events import ProgressNotifierPort

logger = logging.getLogger(__name__)


def create_location_subagent_node(
    location_client: "LocationClientPort",
    event_publisher: "ProgressNotifierPort",
):
    """Location Subagent 노드 생성.

    노드는 thin wrapper로:
    1. 이벤트 발행
    2. LocationService 호출 (gRPC, 비즈니스 로직 위임)
    3. state 업데이트

    Args:
        location_client: Location gRPC 클라이언트
        event_publisher: 이벤트 발행자 (SSE 진행 상황)

    Returns:
        LangGraph 노드 함수
    """
    location_service = LocationService(client=location_client)

    async def location_subagent(state: dict[str, Any]) -> dict[str, Any]:
        """주변 재활용 센터를 검색합니다 (gRPC).

        노드 책임 (Orchestration):
        1. 이벤트 발행 (진행 상황)
        2. 서비스 호출 (gRPC, 비즈니스 로직 위임)
        3. state 업데이트
        """
        job_id = state.get("job_id", "")
        user_location_dict = state.get("user_location")

        # 1. 이벤트: 시작
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="location",
            status="processing",
            progress=50,
            message="📍 위치 정보 확인 중...",
        )

        # 2. 위치 정보 확인
        location_data = _extract_location_data(user_location_dict)
        if location_data is None:
            # 위치 정보 없음 → needs_input 이벤트 발행 (HITL via HTTP)
            await event_publisher.notify_needs_input(
                task_id=job_id,
                input_type="location",
                message="📍 주변 센터를 찾으려면 위치 정보가 필요해요.\n위치 권한을 허용해주세요!",
                timeout=60,
            )
            # 스킵 후 진행 (클라이언트가 위치와 함께 재요청 가능)
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="location",
                status="skipped",
                message="위치 정보 없이 진행합니다.",
            )
            return {
                **state,
                "location_context": None,
                "location_skipped": True,
                "needs_location": True,  # 클라이언트 힌트
            }

        # 3. LocationService로 gRPC 검색
        try:
            centers = await location_service.search_recycling_centers(
                location=location_data,
                radius=5000,  # 5km 반경
                limit=5,  # 최대 5개
            )

            # 4. 컨텍스트 구성
            context = LocationService.to_answer_context(
                locations=centers,
                user_location=location_data,
            )

            logger.info(
                "Location search completed (gRPC)",
                extra={
                    "job_id": job_id,
                    "count": len(centers),
                },
            )

            return {
                **state,
                "location_context": context,
            }

        except Exception as e:
            logger.error(
                "Location gRPC call failed",
                extra={"job_id": job_id, "error": str(e)},
            )
            return {
                **state,
                "location_context": None,
                "subagent_error": "주변 센터 정보를 가져오는 데 실패했어요.",
            }

    return location_subagent


def _extract_location_data(user_location_dict: dict[str, Any] | None) -> LocationData | None:
    """사용자 위치 dict에서 LocationData를 추출."""
    if not user_location_dict:
        return None

    try:
        data = LocationData.from_dict(user_location_dict)
        return data if data.is_valid() else None
    except (KeyError, ValueError):
        return None
