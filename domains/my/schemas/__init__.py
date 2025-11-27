"""
Pydantic schemas for the My domain.
"""

from .user import UserCharacter, UserProfile, UserUpdate

__all__ = ["UserProfile", "UserUpdate", "UserCharacter"]
