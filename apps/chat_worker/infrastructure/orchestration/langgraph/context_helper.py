"""Context Helper for LangGraph Channel Separation.

노드에서 컨텍스트 채널 값을 생성할 때 사용하는 헬퍼 함수.
스케줄링 메타데이터(_priority, _sequence 등)를 자동으로 추가.

사용 예시:
    >>> from ..context_helper import create_context
    >>>
    >>> return {
    >>>     "weather_context": create_context(
    >>>         data={"temperature": 15, "condition": "맑음"},
    >>>         producer="weather",
    >>>         job_id=state.get("job_id", ""),
    >>>     )
    >>> }
"""

from __future__ import annotations

import time
from typing import Any

from .priority import (
    NODE_PRIORITY,
    Priority,
    calculate_effective_priority,
    get_node_deadline,
)
from .sequence import get_sequence


def create_context(
    data: dict[str, Any],
    producer: str,
    job_id: str,
    is_fallback: bool = False,
    deadline_ms: int | None = None,
    success: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    """스케줄링 메타데이터가 포함된 컨텍스트 생성.

    적용 알고리즘:
    1. Priority Scheduling: 노드별 정적 우선순위
    2. Aging: deadline 기반 동적 우선순위 조정 (SLA-driven)
    3. Lamport Clock: sequence로 순서 보장

    Args:
        data: 실제 컨텍스트 데이터
        producer: 생산 노드 이름
        job_id: 작업 ID
        is_fallback: fallback 결과 여부 (우선순위 페널티 적용)
        deadline_ms: 마감 시간 (Aging 계산용), None이면 producer 기반 자동 결정
        success: 성공 여부
        error: 에러 메시지 (실패 시)

    Returns:
        메타데이터가 포함된 컨텍스트 dict:
        - _priority: 유효 우선순위 (낮을수록 높음)
        - _sequence: Lamport Clock 값
        - _producer: 생산 노드 이름
        - _created_at: 생성 시각
        - _is_fallback: fallback 여부
        - success: 성공 여부
        - error: 에러 메시지 (실패 시)
        - **data: 실제 데이터

    Examples:
        >>> # 정상 컨텍스트
        >>> create_context(
        ...     data={"temperature": 15},
        ...     producer="weather",
        ...     job_id="job-123",
        ... )
        {
            "_priority": 75,
            "_sequence": 1,
            "_producer": "weather",
            "_created_at": 1234567890.0,
            "_is_fallback": False,
            "success": True,
            "error": None,
            "temperature": 15,
        }

        >>> # 에러 컨텍스트
        >>> create_context(
        ...     data={},
        ...     producer="weather",
        ...     job_id="job-123",
        ...     success=False,
        ...     error="API timeout",
        ... )
        {
            "_priority": 75,
            "_sequence": 2,
            "_producer": "weather",
            "_created_at": 1234567890.1,
            "_is_fallback": False,
            "success": False,
            "error": "API timeout",
        }
    """
    created_at = time.time()
    base_priority = NODE_PRIORITY.get(producer, Priority.NORMAL)

    # SLA-driven deadline: None이면 producer 기반 자동 결정
    effective_deadline_ms = deadline_ms if deadline_ms is not None else get_node_deadline(producer)

    # Aging 적용
    effective_priority = calculate_effective_priority(
        base_priority=base_priority,
        created_at=created_at,
        deadline_ms=effective_deadline_ms,
        is_fallback=is_fallback,
    )

    # Lamport Clock
    sequence = get_sequence(job_id)

    return {
        # 스케줄링 메타데이터 (underscore prefix)
        "_priority": effective_priority,
        "_sequence": sequence,
        "_producer": producer,
        "_created_at": created_at,
        "_is_fallback": is_fallback,
        # 상태 정보
        "success": success,
        "error": error,
        # 실제 데이터
        **data,
    }


def create_error_context(
    producer: str,
    job_id: str,
    error: str,
    is_fallback: bool = False,
    deadline_ms: int | None = None,
) -> dict[str, Any]:
    """에러 컨텍스트 생성 (편의 함수).

    Args:
        producer: 생산 노드 이름
        job_id: 작업 ID
        error: 에러 메시지
        is_fallback: fallback 결과 여부
        deadline_ms: 마감 시간 (None이면 producer 기반 자동 결정)

    Returns:
        success=False인 컨텍스트
    """
    return create_context(
        data={},
        producer=producer,
        job_id=job_id,
        is_fallback=is_fallback,
        deadline_ms=deadline_ms,  # None → create_context에서 자동 결정
        success=False,
        error=error,
    )


__all__ = [
    "create_context",
    "create_error_context",
]
