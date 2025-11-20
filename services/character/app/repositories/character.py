from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.session import get_db_session


class CharacterRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session

    async def get_character_by_focus(self, focus: str) -> Optional[Character]:
        stmt = select(Character).where(Character.affection_focus == focus).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()
