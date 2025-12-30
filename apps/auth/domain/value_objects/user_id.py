"""UserId Value Object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.auth.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class UserId(ValueObject):
    """사용자 식별자 Value Object.

    UUID를 래핑하여 타입 안전성을 보장합니다.
    """

    value: UUID

    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def from_string(cls, value: str) -> "UserId":
        """문자열에서 UserId 생성."""
        return cls(value=UUID(value))

    @classmethod
    def generate(cls) -> "UserId":
        """새 UserId 생성 (UUID v4)."""
        import uuid

        return cls(value=uuid.uuid4())
