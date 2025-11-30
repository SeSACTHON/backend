"""Pydantic schemas for the Character service."""

from .catalog import CharacterAcquireResponse, CharacterProfile, DefaultCharacterGrantRequest
from .reward import (
    CharacterRewardFailureReason,
    CharacterRewardRequest,
    CharacterRewardResponse,
    CharacterRewardSource,
    ClassificationSummary,
)

__all__ = [
    "CharacterAcquireResponse",
    "CharacterProfile",
    "DefaultCharacterGrantRequest",
    "CharacterRewardSource",
    "CharacterRewardRequest",
    "CharacterRewardResponse",
    "CharacterRewardFailureReason",
    "ClassificationSummary",
]
