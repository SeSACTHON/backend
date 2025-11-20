from fastapi import Depends

from app.repositories.character import CharacterRepository


class CharacterService:
    def __init__(self, character_repository: CharacterRepository = Depends(CharacterRepository)):
        self.character_repository = character_repository

    async def get_character_by_focus(self, focus: str):
        return await self.character_repository.get_character_by_focus(focus)
