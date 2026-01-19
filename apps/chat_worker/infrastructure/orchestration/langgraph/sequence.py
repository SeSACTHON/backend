"""Lamport Clock for LangGraph Event Ordering.

Lamport Logical Clock (Leslie Lamport, 1978):
분산 시스템에서 이벤트의 인과적 순서를 보장하는 논리적 시계.

LangGraph 적용:
- job_id별 독립적인 카운터
- 노드 실행마다 sequence 증가
- Reducer에서 최신 결과 판단에 사용

규칙:
1. 각 이벤트 발생 시 카운터 증가
2. happens-before 관계 보장: a → b 이면 C(a) < C(b)
"""

from __future__ import annotations

from threading import Lock


class LamportClock:
    """Job별 Lamport Logical Clock 구현.

    Thread-safe한 논리적 시계로, 병렬 실행되는 노드들의
    이벤트 순서를 결정하는 데 사용.

    Attributes:
        _counters: job_id별 카운터 저장소
        _lock: Thread-safety를 위한 Lock

    Examples:
        >>> clock = LamportClock()
        >>> seq1 = clock.tick("job-123")  # 1
        >>> seq2 = clock.tick("job-123")  # 2
        >>> seq3 = clock.tick("job-456")  # 1 (다른 job)
        >>> clock.cleanup("job-123")
    """

    def __init__(self) -> None:
        """LamportClock 초기화."""
        self._counters: dict[str, int] = {}
        self._lock = Lock()

    def tick(self, job_id: str) -> int:
        """이벤트 발생 시 호출. 카운터 증가 후 반환.

        Args:
            job_id: 작업 ID

        Returns:
            증가된 카운터 값 (1부터 시작)
        """
        with self._lock:
            self._counters[job_id] = self._counters.get(job_id, 0) + 1
            return self._counters[job_id]

    def get(self, job_id: str) -> int:
        """현재 카운터 값 조회 (증가하지 않음).

        Args:
            job_id: 작업 ID

        Returns:
            현재 카운터 값 (없으면 0)
        """
        return self._counters.get(job_id, 0)

    def cleanup(self, job_id: str) -> None:
        """작업 완료 후 메모리 정리.

        Args:
            job_id: 정리할 작업 ID
        """
        with self._lock:
            self._counters.pop(job_id, None)

    def cleanup_all(self) -> None:
        """모든 카운터 정리 (테스트용)."""
        with self._lock:
            self._counters.clear()

    def __len__(self) -> int:
        """현재 추적 중인 job 수."""
        return len(self._counters)


# ============================================================
# Singleton Instance
# ============================================================

_clock = LamportClock()
"""글로벌 LamportClock 인스턴스.

Worker 프로세스당 하나의 인스턴스 공유.
분산 환경에서는 Redis INCR로 대체 가능.
"""


def get_sequence(job_id: str) -> int:
    """현재 job의 다음 sequence 번호 반환.

    Args:
        job_id: 작업 ID

    Returns:
        증가된 sequence 번호

    Examples:
        >>> seq = get_sequence("job-123")  # 1
        >>> seq = get_sequence("job-123")  # 2
    """
    return _clock.tick(job_id)


def get_current_sequence(job_id: str) -> int:
    """현재 job의 현재 sequence 조회 (증가 없음).

    Args:
        job_id: 작업 ID

    Returns:
        현재 sequence 값
    """
    return _clock.get(job_id)


def cleanup_sequence(job_id: str) -> None:
    """작업 완료 후 sequence 정리.

    Args:
        job_id: 정리할 작업 ID
    """
    _clock.cleanup(job_id)


def get_clock() -> LamportClock:
    """글로벌 LamportClock 인스턴스 반환 (테스트용)."""
    return _clock


__all__ = [
    "LamportClock",
    "cleanup_sequence",
    "get_clock",
    "get_current_sequence",
    "get_sequence",
]
