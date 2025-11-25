from __future__ import annotations

from enum import Enum


class CharacterOwnershipStatus(str, Enum):
    """Represents the lifecycle state of a user's character."""

    OWNED = "owned"
    BURNED = "burned"
    TRADED = "traded"
