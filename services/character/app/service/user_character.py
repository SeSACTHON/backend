from fastapi import Depends, HTTPException

from app.core.config import get_settings
from app.repositories.character import CharacterRepository
from app.repositories.user_character import UserCharacterRepository
from app.schemas import (
    CharacterCatalogEntry,
    CharacterRewardRequest,
    CharacterRewardResult,
    UserCharacterWithDetail,
)


class UserCharacterService:
    def __init__(
        self,
        character_repository: CharacterRepository = Depends(CharacterRepository),
        user_character_repository: UserCharacterRepository = Depends(UserCharacterRepository),
    ):
        self.character_repository = character_repository
        self.user_character_repository = user_character_repository
        self.session = user_character_repository.session
        self.settings = get_settings()

    async def grant_character(self, payload: CharacterRewardRequest) -> CharacterRewardResult:
        threshold = self.settings.classification_min_score
        first_label = payload.labels[0] if payload.labels else None
        if payload.classification_score < threshold:
            return CharacterRewardResult(
                granted=False,
                threshold=threshold,
                guidance=self._build_guidance(first_label, threshold, payload.guidance),
                matched_label=None,
            )

        character, matched_label = await self._match_character(payload.labels)

        user_character = await self.user_character_repository.create_user_character(
            character_id=character.id,
            is_locked=False,
        )
        await self.session.commit()
        await self.session.refresh(user_character)

        detail = self._build_user_character_detail(user_character, character)
        return CharacterRewardResult(
            granted=True,
            threshold=threshold,
            character=detail,
            matched_label=matched_label,
        )

    async def owned_characters(self) -> list[UserCharacterWithDetail]:
        rows = await self.user_character_repository.list_user_characters()
        return [
            self._build_user_character_detail(user_character, character)
            for user_character, character in rows
        ]

    async def _match_character(self, labels: list[str]):
        for label in labels:
            candidate = await self.character_repository.get_character_by_focus(label)
            if candidate:
                return candidate, label
        raise HTTPException(status_code=404, detail="No character available for provided labels")

    @staticmethod
    def _build_user_character_detail(user_character, character) -> UserCharacterWithDetail:
        base_data = UserCharacterWithDetail.model_validate(user_character).model_dump()
        return UserCharacterWithDetail(
            **base_data,
            character=CharacterCatalogEntry.model_validate(character),
        )

    @staticmethod
    def _build_guidance(label, threshold: float, guidance=None) -> str:
        target = label or "해당 폐기물"
        return (
            f"{target} 분류 점수가 기준치({threshold})보다 낮아요. "
            "배출 요령을 다시 확인하고 정확히 분리배출하면 캐릭터가 함께할 수 있어요!"
        )


def get_user_character_service(
    character_repository: CharacterRepository = Depends(CharacterRepository),
    user_character_repository: UserCharacterRepository = Depends(UserCharacterRepository),
) -> UserCharacterService:
    return UserCharacterService(character_repository, user_character_repository)
