from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domains.auth.core.security import now_utc
from domains.auth.models import User, UserSocialAccount
from domains.auth.schemas.oauth import OAuthProfile


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id).options(selectinload(User.social_accounts))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_account_by_provider(
        self,
        provider: str,
        provider_user_id: str,
    ) -> Optional[UserSocialAccount]:
        stmt = (
            select(UserSocialAccount)
            .where(
                UserSocialAccount.provider == provider,
                UserSocialAccount.provider_user_id == provider_user_id,
            )
            .options(selectinload(UserSocialAccount.user).selectinload(User.social_accounts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_account_by_email(self, email: str) -> Optional[UserSocialAccount]:
        stmt = (
            select(UserSocialAccount)
            .where(UserSocialAccount.email == email)
            .options(selectinload(UserSocialAccount.user).selectinload(User.social_accounts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_from_profile(self, profile: OAuthProfile) -> tuple[User, bool]:
        account = await self.get_account_by_provider(profile.provider, profile.provider_user_id)
        now = now_utc()
        created_user = False
        normalized_phone = self._normalize_phone(profile.phone_number)
        if account:
            self._apply_profile(account, profile, last_login_at=now)
            user = account.user
        else:
            user = await self._resolve_user_from_profile(profile)
            if user is None and normalized_phone:
                user = await self._resolve_user_by_name_phone(profile, normalized_phone)
            if user is None:
                user = User(
                    username=profile.name or profile.nickname,
                    nickname=profile.nickname or profile.name,
                    profile_image_url=(
                        str(profile.profile_image_url) if profile.profile_image_url else None
                    ),
                    phone_number=normalized_phone,
                    last_login_at=now,
                )
                self.session.add(user)
                await self.session.flush()
                created_user = True

            account = UserSocialAccount(
                user_id=user.id,
                provider=profile.provider,
                provider_user_id=profile.provider_user_id,
                email=profile.email,
                last_login_at=now,
            )
            self.session.add(account)

        user.last_login_at = now
        if profile.nickname:
            user.nickname = profile.nickname
        if profile.name:
            user.username = profile.name
        if profile.profile_image_url:
            user.profile_image_url = str(profile.profile_image_url)
        if normalized_phone and not user.phone_number:
            user.phone_number = normalized_phone

        await self.session.flush()
        await self.session.refresh(user)
        return user, created_user

    async def touch_last_login(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_login_at=now_utc()),
        )

    async def _resolve_user_from_profile(self, profile: OAuthProfile) -> Optional[User]:
        if profile.email:
            account = await self.get_account_by_email(profile.email)
            if account:
                return account.user
        return None

    async def _resolve_user_by_name_phone(
        self, profile: OAuthProfile, normalized_phone: str
    ) -> Optional[User]:
        normalized_name = (profile.name or profile.nickname or "").strip()
        if not normalized_name or not normalized_phone:
            return None
        stmt = (
            select(User)
            .where(
                func.lower(User.username) == normalized_name.lower(),
                User.phone_number == normalized_phone,
            )
            .options(selectinload(User.social_accounts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        digits = "".join(ch for ch in phone if ch.isdigit())
        return digits or None

    @staticmethod
    def _apply_profile(
        account: UserSocialAccount,
        profile: OAuthProfile,
        *,
        last_login_at: Optional[datetime] = None,
    ) -> None:
        account.email = profile.email or account.email
        if last_login_at:
            account.last_login_at = last_login_at
