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


def _register_defaults() -> None:
    """기본 evaluator 등록."""
    from domains.character.services.evaluators.scan import ScanRewardEvaluator

    register_evaluator(CharacterRewardSource.SCAN, ScanRewardEvaluator())


# 모듈 로드 시 기본 evaluator 등록
_register_defaults()
