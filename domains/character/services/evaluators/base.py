"""Base classes for Reward Evaluators.

Strategy Pattern을 위한 추상 인터페이스 정의.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable, Sequence
from uuid import UUID


if TYPE_CHECKING:
    from domains.character.models import Character
    from domains.character.repositories import CharacterOwnershipRepository, CharacterRepository
    from domains.character.schemas.reward import CharacterRewardRequest

# 타입 안전한 콜백 시그니처
GrantCallback = Callable[
    [UUID, "Character", str],  # (user_id, character, source)
    Awaitable[None],
]


@dataclass
class EvaluationContext:
    """평가에 필요한 의존성을 담는 컨텍스트.

    Attributes:
        character_repo: 캐릭터 조회 레포지토리
        ownership_repo: 소유권 관리 레포지토리
        grant_callback: 캐릭터 지급 콜백 (DB 저장 + gRPC 동기화)
    """

    character_repo: "CharacterRepository"
    ownership_repo: "CharacterOwnershipRepository"
    grant_callback: GrantCallback


@dataclass
class EvaluationResult:
    """평가 결과.

    Attributes:
        should_evaluate: 평가 조건 충족 여부
        matches: 매칭된 캐릭터 목록
        source_label: 리워드 소스 식별자 (예: "scan-reward")
        match_reason: 매칭 사유 문자열
    """

    should_evaluate: bool = False
    matches: Sequence["Character"] = field(default_factory=list)
    source_label: str = ""
    match_reason: str | None = None


class RewardEvaluator(ABC):
    """리워드 평가 추상 클래스 (Strategy Interface).

    새로운 리워드 소스 추가 시 이 클래스를 상속합니다.

    Example:
        class QuestRewardEvaluator(RewardEvaluator):
            SOURCE_LABEL = "quest-reward"

            async def should_evaluate(self, payload):
                return payload.quest_completed

            async def match_characters(self, payload, context):
                # Quest 기반 매칭 로직
                ...
    """

    @property
    @abstractmethod
    def source_label(self) -> str:
        """리워드 소스 식별자 (DB 저장용).

        Returns:
            예: "scan-reward", "quest-reward"
        """
        ...

    @abstractmethod
    async def should_evaluate(self, payload: "CharacterRewardRequest") -> bool:
        """평가 조건을 충족하는지 확인.

        Args:
            payload: 리워드 요청

        Returns:
            bool: 평가를 진행할지 여부
        """
        ...

    @abstractmethod
    async def match_characters(
        self,
        payload: "CharacterRewardRequest",
        context: EvaluationContext,
    ) -> Sequence["Character"]:
        """조건에 맞는 캐릭터 매칭.

        Args:
            payload: 리워드 요청
            context: 평가 컨텍스트

        Returns:
            매칭된 캐릭터 목록 (우선순위 순)
        """
        ...

    @abstractmethod
    def build_match_reason(self, payload: "CharacterRewardRequest") -> str:
        """매칭 사유 문자열 생성.

        Args:
            payload: 리워드 요청

        Returns:
            사람이 읽을 수 있는 매칭 사유
        """
        ...

    async def evaluate(
        self,
        payload: "CharacterRewardRequest",
        context: EvaluationContext,
    ) -> EvaluationResult:
        """평가 실행 (Template Method).

        1. should_evaluate()로 평가 조건 확인
        2. match_characters()로 캐릭터 매칭
        3. 결과 반환 (실제 지급은 상위 레이어에서 처리)

        Args:
            payload: 리워드 요청
            context: 평가 컨텍스트

        Returns:
            평가 결과
        """
        if not await self.should_evaluate(payload):
            return EvaluationResult(should_evaluate=False, source_label=self.source_label)

        match_reason = self.build_match_reason(payload)
        matches = await self.match_characters(payload, context)

        return EvaluationResult(
            should_evaluate=True,
            matches=matches,
            source_label=self.source_label,
            match_reason=match_reason,
        )
