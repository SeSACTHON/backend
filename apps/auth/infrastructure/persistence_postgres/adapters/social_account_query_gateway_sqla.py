"""SQLAlchemy SocialAccount Query Gateway.

SocialAccountQueryGateway 포트의 구현체입니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from apps.auth.domain.entities.user_social_account import UserSocialAccount
from apps.auth.infrastructure.persistence_postgres.mappings.users_social_account import (
    users_social_accounts_table,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlaSocialAccountQueryGateway:
    """SQLAlchemy 기반 SocialAccount Query Gateway.

    SocialAccountQueryGateway 구현체.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    def add(self, social_account: UserSocialAccount) -> None:
        """새 소셜 계정 추가."""
        self._session.add(social_account)

    async def update(self, social_account: UserSocialAccount) -> None:
        """소셜 계정 정보 업데이트."""
        pass  # SQLAlchemy 자동 추적

    async def get_by_provider(
        self, provider: str, provider_user_id: str
    ) -> UserSocialAccount | None:
        """프로바이더 정보로 소셜 계정 조회."""
        stmt = select(UserSocialAccount).where(
            users_social_accounts_table.c.provider == provider,
            users_social_accounts_table.c.provider_user_id == provider_user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
