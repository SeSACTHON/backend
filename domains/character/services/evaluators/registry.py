"""Evaluator Registry.

리워드 소스별 Evaluator를 등록하고 조회합니다.

Usage:
    # 등록
    register_evaluator(CharacterRewardSource.SCAN, ScanRewardEvaluator())

    # 조회
    evaluator = get_evaluator(CharacterRewardSource.SCAN)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.character.schemas.reward import CharacterRewardSource

if TYPE_CHECKING:
    from domains.character.services.evaluators.base import RewardEvaluator

# Global registry
_evaluators: dict[CharacterRewardSource, RewardEvaluator] = {}
_defaults_registered: bool = False


def register_evaluator(source: CharacterRewardSource, evaluator: RewardEvaluator) -> None:
    """Evaluator 등록.

    Args:
        source: 리워드 소스
        evaluator: 해당 소스의 evaluator 인스턴스
    """
    _evaluators[source] = evaluator


def get_evaluator(source: CharacterRewardSource) -> RewardEvaluator | None:
    """소스에 맞는 Evaluator 조회.

    Args:
        source: 리워드 소스

    Returns:
        등록된 evaluator 또는 None
    """
    return _evaluators.get(source)


def reset_registry() -> None:
    """Registry 리셋 후 기본값 재등록 (테스트용).

    테스트 간 상태 격리를 위해 registry를 초기화합니다.

    Usage:
        @pytest.fixture(autouse=True)
        def reset_evaluators():
            reset_registry()
            yield
    """
    global _evaluators, _defaults_registered
    _evaluators = {}
    _defaults_registered = False
    _register_defaults()


def clear_registry() -> None:
    """Registry 완전 초기화 (테스트용).

    기본 evaluator도 등록하지 않고 빈 상태로 만듭니다.
    커스텀 evaluator만 테스트할 때 사용합니다.
    """
    global _evaluators, _defaults_registered
    _evaluators = {}
    _defaults_registered = True  # 자동 재등록 방지


def _register_defaults() -> None:
    """기본 evaluator 등록."""
    global _defaults_registered
    if _defaults_registered:
        return

    from domains.character.services.evaluators.scan import ScanRewardEvaluator

    register_evaluator(CharacterRewardSource.SCAN, ScanRewardEvaluator())
    _defaults_registered = True


# 모듈 로드 시 기본 evaluator 등록
_register_defaults()
