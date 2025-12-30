"""Flusher Port.

세션 변경사항 플러시를 위한 인터페이스입니다.
"""

from typing import Protocol


class Flusher(Protocol):
    """세션 플러시 인터페이스.

    Session의 변경사항을 DB에 반영합니다 (commit 전).

    구현체:
        - SqlaFlusher (infrastructure/adapters/)
    """

    async def flush(self) -> None:
        """세션 변경사항 플러시.

        커밋하지 않고 변경사항만 DB에 반영합니다.
        """
        ...
