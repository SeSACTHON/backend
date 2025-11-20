from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class CharacterCatalogEntry(BaseModel):
    id: UUID
    code: str
    name: str
    affection_focus: str
    description: Optional[str] = None
    traits: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCharacterResponse(BaseModel):
    id: UUID
    character_id: UUID
    is_locked: bool
    affection_score: int
    classification_count: int
    acquired_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCharacterWithDetail(UserCharacterResponse):
    character: CharacterCatalogEntry


class CharacterRewardRequest(BaseModel):
    labels: List[str] = Field(min_length=1)
    classification_score: float = Field(ge=0.0, le=1.0)
    guidance: Optional[str] = None
    is_locked: bool = True


class CharacterRewardResult(BaseModel):
    granted: bool
    threshold: float
    character: Optional[UserCharacterWithDetail] = None
    guidance: Optional[str] = None
    matched_label: Optional[str] = None
