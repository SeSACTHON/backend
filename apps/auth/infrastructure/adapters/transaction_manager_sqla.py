"""SQLAlchemy Transaction Manager.

TransactionManager 포트의 구현체입니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlaTransactionManager:
    """SQLAlchemy 트랜잭션 관리자.

    TransactionManager 구현체.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def commit(self) -> None:
        """트랜잭션 커밋."""
        await self._session.commit()

    async def rollback(self) -> None:
        """트랜잭션 롤백."""
        await self._session.rollback()
