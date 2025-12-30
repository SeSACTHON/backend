"""TransactionManager Port.

트랜잭션 관리를 위한 인터페이스입니다.
"""

from typing import Protocol


class TransactionManager(Protocol):
    """트랜잭션 관리 인터페이스.

    구현체:
        - SqlaTransactionManager (infrastructure/adapters/)
    """

    async def commit(self) -> None:
        """트랜잭션 커밋."""
        ...

    async def rollback(self) -> None:
        """트랜잭션 롤백."""
        ...
