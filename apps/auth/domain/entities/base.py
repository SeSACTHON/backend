"""Entity Base Class.

Clean Architecture에서 Entity는:
- 고유한 식별자(ID)를 가짐
- 비즈니스 규칙과 상태를 캡슐화
- ORM과 분리된 순수 Python 객체

Reference:
    https://github.com/ivan-borovets/fastapi-clean-example/blob/master/src/app/domain/entities/base.py
"""

from __future__ import annotations

from typing import Generic, Hashable, TypeVar

T = TypeVar("T", bound=Hashable)


class Entity(Generic[T]):
    """모든 Entity의 베이스 클래스.

    Generic[T]로 ID 타입을 명시합니다.
    - Entity[UserId]: 사용자 엔티티
    - Entity[UUID]: UUID를 직접 사용하는 경우

    Example:
        >>> class User(Entity[UserId]):
        ...     def __init__(self, *, id_: UserId, username: str):
        ...         super().__init__(id_=id_)
        ...         self.username = username
    """

    __slots__ = ("id_",)

    def __init__(self, *, id_: T) -> None:
        self.id_: T = id_

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id_ == other.id_

    def __hash__(self) -> int:
        return hash(self.id_)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id_={self.id_!r})"
