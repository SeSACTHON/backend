from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.models.user import User
from app.schemas.oauth import OAuthProfile


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_provider(self, provider: str, provider_user_id: str) -> Optional[User]:
        stmt = select(User).where(
            User.provider == provider,
            User.provider_user_id == provider_user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_from_profile(self, profile: OAuthProfile) -> User:
        existing = await self.get_by_provider(profile.provider, profile.provider_user_id)
        if existing:
            existing.email = profile.email or existing.email
            existing.nickname = profile.nickname or existing.nickname
            existing.username = profile.name or existing.username
            existing.profile_image_url = profile.profile_image_url or existing.profile_image_url
            existing.last_login_at = now_utc()
            await self.session.flush()
            return existing

        user = User(
            provider=profile.provider,
            provider_user_id=profile.provider_user_id,
            email=profile.email,
            nickname=profile.nickname or profile.name,
            username=profile.name or profile.nickname,
            profile_image_url=profile.profile_image_url,
            last_login_at=now_utc(),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def touch_last_login(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_login_at=now_utc()),
        )
