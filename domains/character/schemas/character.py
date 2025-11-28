from __future__ import annotations

from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    id: str
    name: str
    description: str
    compatibility_score: float
    traits: List[str]


class DefaultCharacterGrantRequest(BaseModel):
    user_id: UUID


class CharacterSummary(BaseModel):
    name: str
    dialog: str | None = None


class CharacterAcquireResponse(BaseModel):
    acquired: bool = Field(description="True when the character was newly unlocked")
    character: CharacterSummary
