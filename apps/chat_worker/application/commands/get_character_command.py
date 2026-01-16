"""Get Character Command.

캐릭터 정보 조회 UseCase.

Clean Architecture:
- Command(UseCase): 이 파일 - Port 호출, 오케스트레이션
- Service: CategoryExtractorService, CharacterService - 순수 비즈니스 로직 (Port 의존 없음)
- Port: LLMClientPort, CharacterClientPort, PromptLoaderPort, CharacterAssetPort - 외부 의존
- Node(Adapter): character_node.py - LangGraph glue

구조:
- Command: LLM 호출, Character API 호출, Asset 로딩, Service 호출, 오케스트레이션
- Service: 프롬프트 구성, 결과 파싱, 컨텍스트 변환
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from chat_worker.application.services.category_extractor import CategoryExtractorService
from chat_worker.application.services.character_service import CharacterService

if TYPE_CHECKING:
    from chat_worker.application.ports.character_asset import CharacterAssetPort
    from chat_worker.application.ports.character_client import CharacterClientPort
    from chat_worker.application.ports.llm import LLMClientPort
    from chat_worker.application.ports.prompt_loader import PromptLoaderPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GetCharacterInput:
    """Command 입력 DTO."""

    job_id: str
    message: str


@dataclass
class GetCharacterOutput:
    """Command 출력 DTO."""

    success: bool
    character_context: dict[str, Any] | None = None
    error_message: str | None = None
    events: list[str] = field(default_factory=list)


class GetCharacterCommand:
    """캐릭터 정보 조회 Command (UseCase).

    Port 호출 + 오케스트레이션:
    1. LLM 호출 - 카테고리 추출 (LLMClientPort)
    2. Service 호출 - 결과 파싱 (순수 로직)
    3. API 호출 - 캐릭터 조회 (CharacterClientPort)
    4. Asset 로딩 - CDN에서 캐릭터 이미지 (CharacterAssetPort, 선택)
    5. Service 호출 - 컨텍스트 변환 (순수 로직)

    Port 주입:
    - llm: 카테고리 추출용
    - character_client: 캐릭터 조회용
    - prompt_loader: 프롬프트 로딩용
    - character_asset_loader: 캐릭터 에셋 로딩용 (선택)
    """

    def __init__(
        self,
        llm: "LLMClientPort",
        character_client: "CharacterClientPort",
        prompt_loader: "PromptLoaderPort",
        character_asset_loader: "CharacterAssetPort | None" = None,
    ) -> None:
        """Command 초기화.

        Args:
            llm: LLM 클라이언트
            character_client: Character gRPC 클라이언트
            prompt_loader: 프롬프트 로더
            character_asset_loader: 캐릭터 에셋 로더 (선택)
        """
        self._llm = llm
        self._character_client = character_client
        self._asset_loader = character_asset_loader

        # Service 생성 (Port 없이 문자열만 전달)
        self._category_extractor = CategoryExtractorService(prompt_loader)

    async def execute(self, input_dto: GetCharacterInput) -> GetCharacterOutput:
        """Command 실행.

        Args:
            input_dto: 입력 DTO

        Returns:
            출력 DTO
        """
        events: list[str] = []

        # 1. 프롬프트 구성 (Service - 순수 로직)
        prompt = self._category_extractor.build_extraction_prompt(input_dto.message)
        system_prompt = self._category_extractor.get_system_prompt()

        # 2. LLM 호출 (Command에서 Port 호출)
        try:
            llm_response = await self._llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=20,
                temperature=0.1,
            )
            events.append("llm_called")
        except Exception as e:
            logger.error(
                "LLM call failed",
                extra={"job_id": input_dto.job_id, "error": str(e)},
            )
            events.append("llm_error")
            return GetCharacterOutput(
                success=False,
                error_message="죄송해요, 질문을 이해하지 못했어요.",
                events=events,
            )

        # 3. 결과 파싱 (Service - 순수 로직)
        extraction_result = self._category_extractor.parse_extraction_result(
            llm_response
        )
        events.append("category_extraction_completed")

        if not extraction_result.success:
            events.append("category_extraction_failed")
            return GetCharacterOutput(
                success=False,
                error_message=extraction_result.error_message,
                events=events,
            )

        waste_category = extraction_result.category
        logger.info(
            "Category extracted",
            extra={"job_id": input_dto.job_id, "category": waste_category},
        )

        # 4. Character API 호출 (Command에서 Port 호출)
        try:
            character = await self._character_client.get_character_by_waste_category(
                waste_category
            )
            events.append("character_api_called")
        except Exception as e:
            logger.error(
                "Character API call failed",
                extra={"job_id": input_dto.job_id, "error": str(e)},
            )
            events.append("character_api_error")
            return GetCharacterOutput(
                success=False,
                error_message="캐릭터 정보를 가져오는 데 실패했어요.",
                events=events,
            )

        # 5. 컨텍스트 구성 (Service - 순수 로직)
        if not CharacterService.validate_character(character):
            events.append("character_not_found")
            return GetCharacterOutput(
                success=True,
                character_context=CharacterService.build_not_found_context(
                    waste_category
                ),
                events=events,
            )

        char_context = CharacterService.build_found_context(character, waste_category)
        events.append("character_found")

        # 6. Asset 로딩 (선택) - 이미지 생성 참조용
        if self._asset_loader and character.code:
            cdn_code = CharacterService.to_cdn_code(character.code)
            if cdn_code:
                try:
                    asset = await self._asset_loader.get_asset(cdn_code)
                    if asset:
                        char_context["asset"] = {
                            "code": asset.code,
                            "image_url": asset.image_url,
                            "image_bytes": asset.image_bytes,
                        }
                        events.append("asset_loaded")
                        logger.info(
                            "Character asset loaded",
                            extra={
                                "job_id": input_dto.job_id,
                                "cdn_code": cdn_code,
                                "size": len(asset.image_bytes) if asset.image_bytes else 0,
                            },
                        )
                    else:
                        events.append("asset_not_found")
                        logger.warning(
                            "Character asset not found",
                            extra={"job_id": input_dto.job_id, "cdn_code": cdn_code},
                        )
                except Exception as e:
                    # Asset 로딩 실패는 non-critical (FAIL_OPEN)
                    events.append("asset_load_error")
                    logger.warning(
                        "Character asset load failed (non-critical)",
                        extra={"job_id": input_dto.job_id, "cdn_code": cdn_code, "error": str(e)},
                    )

        logger.info(
            "Character found",
            extra={
                "job_id": input_dto.job_id,
                "character_name": character.name,
                "has_asset": "asset" in char_context,
            },
        )

        return GetCharacterOutput(
            success=True,
            character_context=char_context,
            events=events,
        )
