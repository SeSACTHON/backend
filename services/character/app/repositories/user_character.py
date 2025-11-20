from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.character import Character
from app.database.models.user_character import UserCharacter
from app.database.session import get_db_session
from app.dependencies.security import access_token_dependency
from services._shared.security import TokenPayload


class UserCharacterRepository:
    def __init__(
        self,
        session: AsyncSession = Depends(get_db_session),
        current_user: TokenPayload = Depends(access_token_dependency),
    ):
        self.session = session
        self.current_user = current_user

    async def create_user_character(
        self,
        *,
        character_id: UUID,
        is_locked: bool,
    ) -> UserCharacter:
        if not is_locked:
            existing = await self.get_user_character(character_id=character_id)
            if existing:
                existing.is_locked = False
                existing.affection_score += 1
                return existing

        user_character = UserCharacter(
            user_id=self.current_user.user_id,
            character_id=character_id,
            is_locked=is_locked,
            classification_count=1,
            affection_score=1,
        )
        self.session.add(user_character)
        await self.session.flush()
        return user_character

    async def get_user_character(self, *, character_id: UUID) -> Optional[UserCharacter]:
        stmt = (
            select(UserCharacter)
            .where(
                UserCharacter.user_id == self.current_user.user_id,
                UserCharacter.character_id == character_id,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_user_characters(self) -> Sequence[tuple[UserCharacter, Character]]:
        stmt = (
            select(UserCharacter, Character)
            .join(Character, Character.id == UserCharacter.character_id)
            .where(UserCharacter.user_id == self.current_user.user_id)
            .order_by(UserCharacter.acquired_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.all()
