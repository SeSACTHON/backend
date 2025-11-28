from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.character.database.session import get_db_session
from domains.character.models import Character
from domains.character.repositories import CharacterOwnershipRepository, CharacterRepository
from domains.character.schemas.character import (
    CharacterAcquireResponse,
    CharacterProfile,
    CharacterSummary,
)
from domains.character.schemas.reward import (
    CharacterRewardFailureReason,
    CharacterRewardRequest,
    CharacterRewardResponse,
    CharacterRewardSource,
    ClassificationSummary,
)

DEFAULT_CHARACTER_NAME = "이코"
DEFAULT_CHARACTER_SOURCE = "default-onboard"


class CharacterService:
    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session
        self.character_repo = CharacterRepository(session)
        self.ownership_repo = CharacterOwnershipRepository(session)

    async def catalog(self) -> list[CharacterProfile]:
        characters = await self.character_repo.list_all()
        if not characters:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="등록된 캐릭터가 없습니다.",
            )
        return [self._to_profile(character) for character in characters]

    async def grant_default_character(self, user_id: UUID) -> CharacterAcquireResponse:
        return await self._grant_character_by_name(
            user_id=user_id,
            character_name=DEFAULT_CHARACTER_NAME,
            source=DEFAULT_CHARACTER_SOURCE,
            allow_empty=True,
        )

    async def metrics(self) -> dict:
        return {
            "analyzed_users": 128,
            "catalog_size": 5,
            "history_entries": 56,
        }

    async def evaluate_reward(self, payload: CharacterRewardRequest) -> CharacterRewardResponse:
        classification = payload.classification
        reward_summary: CharacterSummary | None = None
        already_owned = False
        received = False
        match_reason: str | None = None

        should_evaluate = (
            payload.source == CharacterRewardSource.SCAN
            and classification.major_category.strip() == "재활용폐기물"
            and payload.disposal_rules_present
            and not payload.insufficiencies_present
        )

        if should_evaluate:
            match_reason = self._build_match_reason(classification)
            matches = await self._match_characters(classification)
            if matches:
                reward_summary, already_owned, failure_reason = await self._apply_reward(
                    payload.user_id, matches
                )
                received = (
                    failure_reason is None and reward_summary is not None and not already_owned
                )

        return self._to_reward_response(reward_summary, already_owned, received, match_reason)

    @staticmethod
    def _to_summary(character) -> CharacterSummary:
        metadata = getattr(character, "metadata_json", None) or {}
        dialog_value = metadata.get("dialog") or metadata.get("dialogue")
        dialog = str(dialog_value).strip() if dialog_value else None
        return CharacterSummary(
            name=character.name,
            dialog=dialog,
        )

    @staticmethod
    def _to_reward_response(
        summary: CharacterSummary | None,
        already_owned: bool,
        received: bool,
        match_reason: str | None,
    ) -> CharacterRewardResponse:
        return CharacterRewardResponse(
            received=received,
            already_owned=already_owned,
            name=summary.name if summary else None,
            dialog=summary.dialog if summary else None,
            match_reason=match_reason,
        )

    async def _grant_character_by_name(
        self,
        *,
        user_id: UUID,
        character_name: str,
        source: str,
        allow_empty: bool,
    ) -> CharacterAcquireResponse:
        normalized_name = character_name.strip()
        if not normalized_name:
            if allow_empty:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default character name is not configured",
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Character name required",
            )

        character = await self.character_repo.get_by_name(normalized_name)
        if character is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

        existing = await self.ownership_repo.get_by_user_and_character(
            user_id=user_id,
            character_id=character.id,
        )
        if existing:
            return CharacterAcquireResponse(acquired=False, character=self._to_summary(character))

        await self.ownership_repo.upsert_owned(
            user_id=user_id,
            character=character,
            source=source,
        )
        await self.session.commit()
        return CharacterAcquireResponse(acquired=True, character=self._to_summary(character))

    async def _match_characters(self, classification: ClassificationSummary) -> list[Character]:
        match_label = self._resolve_match_label(classification)
        if not match_label:
            return []
        return await self.character_repo.list_by_match_label(match_label)

    @staticmethod
    def _resolve_match_label(classification: ClassificationSummary) -> str | None:
        major = (classification.major_category or "").strip()
        middle = (classification.middle_category or "").strip()
        if major == "재활용폐기물":
            return middle or None
        return middle or major or None

    @staticmethod
    def _build_match_reason(classification: ClassificationSummary) -> str:
        middle = (classification.middle_category or "").strip()
        minor = (classification.minor_category or "").strip()
        if middle and minor:
            return f"{middle}>{minor}"
        if middle:
            return middle
        major = (classification.major_category or "").strip()
        if major:
            return major
        return "미정의"

    async def _apply_reward(
        self,
        user_id: UUID,
        matches: Sequence[Character],
    ) -> tuple[CharacterSummary | None, bool, CharacterRewardFailureReason | None]:
        for match in matches:
            existing = await self.ownership_repo.get_by_user_and_character(
                user_id=user_id, character_id=match.id
            )
            if existing:
                return self._to_summary(match), True, None

            await self.ownership_repo.upsert_owned(
                user_id=user_id,
                character=match,
                source="scan-reward",
            )
            await self.session.commit()
            return self._to_summary(match), False, None

        return None, False, CharacterRewardFailureReason.CHARACTER_NOT_FOUND

    @staticmethod
    def _to_profile(character: Character) -> CharacterProfile:
        metadata = getattr(character, "metadata_json", None) or {}
        description = CharacterService._extract_description(character, metadata)
        traits = CharacterService._extract_traits(metadata, character.match_label)
        compatibility_score = CharacterService._estimate_compatibility(traits)
        identifier = character.code or str(character.id)
        return CharacterProfile(
            id=identifier,
            name=character.name,
            description=description,
            compatibility_score=compatibility_score,
            traits=traits,
        )

    @staticmethod
    def _extract_description(character: Character, metadata: dict) -> str:
        dialog = metadata.get("dialog") or metadata.get("dialogue")
        description = (dialog or character.description or "").strip()
        if description:
            return description
        return f"{character.name}와 함께 친환경 습관을 만들어보세요!"

    @staticmethod
    def _extract_traits(metadata: dict, match_label: str | None) -> list[str]:
        type_field = metadata.get("type") or metadata.get("types") or ""
        normalized = [
            trait.strip()
            for trait in type_field.replace("/", ",").split(",")
            if trait and trait.strip()
        ]
        if normalized:
            return normalized
        label = (match_label or "").strip()
        if label:
            return [label]
        return ["제로웨이스트"]

    @staticmethod
    def _estimate_compatibility(traits: list[str]) -> float:
        base = 0.75
        bonus = min(len(traits), 8) * 0.025
        return round(min(base + bonus, 0.98), 2)
