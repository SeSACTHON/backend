"""SQLAlchemy Flusher.

Flusher 포트의 구현체입니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlaFlusher:
    """SQLAlchemy 세션 플러시.

    Flusher 구현체.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def flush(self) -> None:
        """세션 변경사항 플러시."""
        await self._session.flush()
