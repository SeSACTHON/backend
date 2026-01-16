"""Character Service - 순수 비즈니스 로직.

Port 의존 없이 순수 로직만 담당:
- 컨텍스트 변환 (to_answer_context)
- 결과 검증
- 캐릭터 코드 변환

Port 호출(API)은 Command에서 담당.

Clean Architecture:
- Service: 이 파일 (순수 로직, Port 의존 없음)
- Command: GetCharacterCommand (Port 호출, 오케스트레이션)
- DTO: CharacterDTO
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chat_worker.application.ports.character_client import CharacterDTO

logger = logging.getLogger(__name__)


class CharacterService:
    """캐릭터 비즈니스 로직 서비스 (순수 로직).

    Port 의존 없이 순수 비즈니스 로직만 담당:
    - 컨텍스트 변환 (to_answer_context)
    - 결과 검증
    - 캐릭터 코드 변환

    API 호출은 Command에서 담당.
    """

    # 캐릭터 코드 접두사 (DB: "char-pet" → CDN: "pet")
    CHARACTER_CODE_PREFIX = "char-"

    @staticmethod
    def to_cdn_code(character_code: str | None) -> str | None:
        """캐릭터 코드를 CDN 코드로 변환.

        DB의 캐릭터 코드는 "char-pet" 형식이고,
        CDN의 에셋 코드는 "pet" 형식입니다.

        Args:
            character_code: DB의 캐릭터 코드 (예: "char-pet")

        Returns:
            CDN 에셋 코드 (예: "pet") 또는 None
        """
        if not character_code:
            return None

        if character_code.startswith(CharacterService.CHARACTER_CODE_PREFIX):
            return character_code[len(CharacterService.CHARACTER_CODE_PREFIX) :]

        # 접두사가 없으면 그대로 반환 (이미 CDN 코드일 수 있음)
        return character_code

    @staticmethod
    def to_answer_context(character: "CharacterDTO") -> dict[str, Any]:
        """Answer 노드용 컨텍스트 생성.

        Args:
            character: 캐릭터 DTO

        Returns:
            Answer 노드용 컨텍스트 딕셔너리
        """
        return {
            "name": character.name,
            "type": character.type_label,
            "dialog": character.dialog,
            "match_reason": character.match_label,
            "code": character.code,  # CDN 에셋 조회용
        }

    @staticmethod
    def validate_character(character: "CharacterDTO | None") -> bool:
        """캐릭터 유효성 검증.

        Args:
            character: 캐릭터 DTO (None일 수 있음)

        Returns:
            유효 여부
        """
        if character is None:
            return False
        return bool(character.name)

    @staticmethod
    def build_not_found_context(waste_category: str) -> dict[str, Any]:
        """캐릭터 없음 컨텍스트 생성.

        Args:
            waste_category: 폐기물 카테고리

        Returns:
            캐릭터 없음 컨텍스트
        """
        return {
            "waste_category": waste_category,
            "found": False,
            "message": f"'{waste_category}' 카테고리의 캐릭터를 찾지 못했어요.",
        }

    @staticmethod
    def build_found_context(
        character: "CharacterDTO",
        waste_category: str,
    ) -> dict[str, Any]:
        """캐릭터 찾음 컨텍스트 생성.

        Args:
            character: 캐릭터 DTO
            waste_category: 폐기물 카테고리

        Returns:
            캐릭터 찾음 컨텍스트
        """
        context = CharacterService.to_answer_context(character)
        context["waste_category"] = waste_category
        context["found"] = True
        return context
