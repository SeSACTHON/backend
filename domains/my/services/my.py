from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.my.database.session import get_db_session
from domains.my.models import User
from domains.my.repositories import UserRepository
from domains.my.schemas import UserProfile, UserUpdate


class MyService:
    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session
        self.repo = UserRepository(session)

    async def get_user(self, user_id: int) -> UserProfile:
        user = await self.repo.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._to_profile(user)

    async def update_user(self, user_id: int, payload: UserUpdate) -> UserProfile:
        user = await self.repo.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        updated = await self.repo.update_user(user, payload.dict(exclude_none=True))
        await self.session.commit()
        return self._to_profile(updated)

    async def delete_user(self, user_id: int) -> None:
        user = await self.repo.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        await self.repo.delete_user(user_id)
        await self.session.commit()

    async def metrics(self) -> dict:
        return await self.repo.metrics()

    @staticmethod
    def _to_profile(user: User) -> UserProfile:
        return UserProfile(
            id=int(user.id),
            provider=user.provider,
            provider_user_id=user.provider_user_id,
            email=user.email,
            username=user.username,
            name=user.name,
            profile_image_url=user.profile_image_url,
            created_at=user.created_at,
        )
