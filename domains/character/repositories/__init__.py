"""Repository layer for the Character domain."""

from .character_repository import CharacterRepository
from .ownership_repository import CharacterOwnershipRepository

__all__ = ["CharacterRepository", "CharacterOwnershipRepository"]
