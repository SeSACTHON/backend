"""SQLAlchemy Users Command Gateway.

UsersCommandGateway 포트의 구현체입니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete

from apps.auth.domain.entities.user import User
from apps.auth.domain.value_objects.user_id import UserId
from apps.auth.infrastructure.persistence_postgres.mappings.users import users_table

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlaUsersCommandGateway:
    """SQLAlchemy 기반 Users Command Gateway.

    UsersCommandGateway 구현체.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    def add(self, user: User) -> None:
        """새 사용자 추가.

        Session에 추가만 하고 커밋은 TransactionManager에서 처리합니다.
        """
        self._session.add(user)

    async def update(self, user: User) -> None:
        """사용자 정보 업데이트.

        변경된 속성은 Session에서 자동으로 추적됩니다.
        """
        # SQLAlchemy가 변경사항을 자동 추적
        pass

    async def delete(self, user_id: UserId) -> None:
        """사용자 삭제."""
        stmt = delete(users_table).where(users_table.c.id == user_id.value)
        await self._session.execute(stmt)
