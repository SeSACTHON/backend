from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    name: str
    type: str
    dialog: str
    match: Optional[str] = None


class DefaultCharacterGrantRequest(BaseModel):
    user_id: UUID


class CharacterAcquireResponse(BaseModel):
    acquired: bool = Field(description="True when the character was newly unlocked")
    character: CharacterProfile
