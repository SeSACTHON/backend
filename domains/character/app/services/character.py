from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.character.app.schemas.character import (
    CharacterAcquireRequest,
    CharacterAcquireResponse,
    CharacterProfile,
    CharacterSummary,
)
from domains.character.database.session import get_db_session
from domains.character.repositories import CharacterOwnershipRepository, CharacterRepository


class CharacterService:
    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session
        self.character_repo = CharacterRepository(session)
        self.ownership_repo = CharacterOwnershipRepository(session)

    async def catalog(self) -> list[CharacterProfile]:
        return [
            CharacterProfile(
                id="catalog-guardian",
                name="Guardian",
                description="Protects nature and educates neighbors.",
                compatibility_score=0.93,
                traits=["educator", "community-builder"],
            ),
            CharacterProfile(
                id="catalog-strategist",
                name="Strategist",
                description="Optimizes recycling routes and logistics.",
                compatibility_score=0.85,
                traits=["analyst", "planner"],
            ),
        ]

    async def acquire_character(self, payload: CharacterAcquireRequest) -> CharacterAcquireResponse:
        character_name = payload.character_name.strip()
        if not character_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Character name required"
            )

        character = await self.character_repo.get_by_name(character_name)
        if character is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

        existing = await self.ownership_repo.get_by_user_and_character(
            user_id=payload.user_id, character_id=character.id
        )
        if existing:
            return CharacterAcquireResponse(acquired=False, character=self._to_summary(character))

        await self.ownership_repo.upsert_owned(
            user_id=payload.user_id,
            character=character,
            source="api-acquire",
        )
        await self.session.commit()
        return CharacterAcquireResponse(acquired=True, character=self._to_summary(character))

    async def metrics(self) -> dict:
        return {
            "analyzed_users": 128,
            "catalog_size": 5,
            "history_entries": 56,
        }

    @staticmethod
    def _to_summary(character) -> CharacterSummary:
        return CharacterSummary(
            id=character.id,
            code=character.code,
            name=character.name,
            rarity=character.rarity,
            description=character.description,
            metadata=character.metadata_json,
        )
