"""UsersService gRPC Servicer.

OAuth 콜백에서 auth 도메인이 호출하는 사용자 관련 gRPC 서비스입니다.

Phase 1: auth 스키마 테이블 사용 (임시)
Phase 2: users 스키마로 마이그레이션 예정

참고: https://rooftopsnow.tistory.com/127
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import grpc

from apps.users.infrastructure.grpc import users_pb2, users_pb2_grpc
from apps.users.infrastructure.persistence_postgres.mappings.auth_user import (
    AuthUserModel,
    AuthSocialAccountModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UsersServicer(users_pb2_grpc.UsersServiceServicer):
    """Users gRPC Service 구현.

    Phase 1에서는 auth.users, auth.user_social_accounts 테이블에 접근합니다.
    Phase 2에서 users 스키마로 마이그레이션됩니다.
    """

    def __init__(self, session_factory) -> None:
        """
        Args:
            session_factory: AsyncSession 팩토리 함수
        """
        self._session_factory = session_factory

    async def GetOrCreateFromOAuth(
        self,
        request: users_pb2.GetOrCreateFromOAuthRequest,
        context: grpc.aio.ServicerContext,
    ) -> users_pb2.GetOrCreateFromOAuthResponse:
        """OAuth 프로필로 사용자 조회 또는 생성."""
        try:
            async with self._session_factory() as session:
                # 1. 기존 사용자 조회 (provider + provider_user_id로)
                existing = await self._get_user_by_provider(
                    session,
                    request.provider,
                    request.provider_user_id,
                )

                if existing:
                    user, social_account = existing
                    logger.info(
                        "Found existing user via OAuth",
                        extra={
                            "user_id": str(user.id),
                            "provider": request.provider,
                        },
                    )
                    return users_pb2.GetOrCreateFromOAuthResponse(
                        user=self._user_to_proto(user),
                        social_account=self._social_account_to_proto(social_account),
                        is_new_user=False,
                    )

                # 2. 새 사용자 생성
                user, social_account = await self._create_user_from_oauth(
                    session,
                    provider=request.provider,
                    provider_user_id=request.provider_user_id,
                    email=request.email if request.HasField("email") else None,
                    nickname=request.nickname if request.HasField("nickname") else None,
                    profile_image_url=(
                        request.profile_image_url if request.HasField("profile_image_url") else None
                    ),
                )

                await session.commit()

                logger.info(
                    "Created new user via OAuth",
                    extra={
                        "user_id": str(user.id),
                        "provider": request.provider,
                    },
                )

                return users_pb2.GetOrCreateFromOAuthResponse(
                    user=self._user_to_proto(user),
                    social_account=self._social_account_to_proto(social_account),
                    is_new_user=True,
                )

        except ValueError as e:
            logger.error("Invalid argument in GetOrCreateFromOAuth", extra={"error": str(e)})
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception:
            logger.exception("Internal error in GetOrCreateFromOAuth")
            await context.abort(grpc.StatusCode.INTERNAL, "Internal server error")

    async def GetUser(
        self,
        request: users_pb2.GetUserRequest,
        context: grpc.aio.ServicerContext,
    ) -> users_pb2.GetUserResponse:
        """사용자 ID로 조회."""
        try:
            user_id = UUID(request.user_id)

            async with self._session_factory() as session:
                user = await self._get_user_by_id(session, user_id)

                if user is None:
                    return users_pb2.GetUserResponse()

                return users_pb2.GetUserResponse(user=self._user_to_proto(user))

        except ValueError as e:
            logger.error("Invalid user_id format", extra={"error": str(e)})
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception:
            logger.exception("Internal error in GetUser")
            await context.abort(grpc.StatusCode.INTERNAL, "Internal server error")

    async def UpdateLoginTime(
        self,
        request: users_pb2.UpdateLoginTimeRequest,
        context: grpc.aio.ServicerContext,
    ) -> users_pb2.UpdateLoginTimeResponse:
        """로그인 시간 업데이트."""
        try:
            user_id = UUID(request.user_id)

            async with self._session_factory() as session:
                success = await self._update_login_time(
                    session,
                    user_id=user_id,
                    provider=request.provider,
                    provider_user_id=request.provider_user_id,
                )
                await session.commit()

                return users_pb2.UpdateLoginTimeResponse(success=success)

        except ValueError as e:
            logger.error("Invalid argument in UpdateLoginTime", extra={"error": str(e)})
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception:
            logger.exception("Internal error in UpdateLoginTime")
            await context.abort(grpc.StatusCode.INTERNAL, "Internal server error")

    # =========================================================================
    # Private Methods - DB Operations (Phase 1: auth 스키마 사용)
    # =========================================================================

    async def _get_user_by_provider(
        self,
        session: "AsyncSession",
        provider: str,
        provider_user_id: str,
    ) -> tuple[AuthUserModel, AuthSocialAccountModel] | None:
        """Provider 정보로 사용자 조회."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AuthUserModel)
            .join(AuthSocialAccountModel)
            .where(
                AuthSocialAccountModel.provider == provider,
                AuthSocialAccountModel.provider_user_id == provider_user_id,
            )
            .options(selectinload(AuthUserModel.social_accounts))
        )

        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            return None

        # 해당 소셜 계정 찾기
        social_account = next(
            (
                acc
                for acc in user.social_accounts
                if acc.provider == provider and acc.provider_user_id == provider_user_id
            ),
            None,
        )

        return user, social_account

    async def _get_user_by_id(self, session: "AsyncSession", user_id: UUID) -> AuthUserModel | None:
        """ID로 사용자 조회."""
        from sqlalchemy import select

        stmt = select(AuthUserModel).where(AuthUserModel.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_user_from_oauth(
        self,
        session: "AsyncSession",
        *,
        provider: str,
        provider_user_id: str,
        email: str | None,
        nickname: str | None,
        profile_image_url: str | None,
    ) -> tuple[AuthUserModel, AuthSocialAccountModel]:
        """OAuth 프로필로 새 사용자 생성."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()

        user = AuthUserModel()
        user.id = user_id
        user.username = None
        user.nickname = nickname
        user.profile_image_url = profile_image_url
        user.phone_number = None
        user.created_at = now
        user.updated_at = now
        user.last_login_at = now

        social_account = AuthSocialAccountModel()
        social_account.id = uuid4()
        social_account.user_id = user_id
        social_account.provider = provider
        social_account.provider_user_id = provider_user_id
        social_account.email = email
        social_account.last_login_at = now
        social_account.created_at = now
        social_account.updated_at = now

        session.add(user)
        session.add(social_account)

        return user, social_account

    async def _update_login_time(
        self,
        session: "AsyncSession",
        *,
        user_id: UUID,
        provider: str,
        provider_user_id: str,
    ) -> bool:
        """로그인 시간 업데이트."""
        from sqlalchemy import update

        now = datetime.now(timezone.utc)

        # User last_login_at 업데이트
        await session.execute(
            update(AuthUserModel)
            .where(AuthUserModel.id == user_id)
            .values(last_login_at=now, updated_at=now)
        )

        # SocialAccount last_login_at 업데이트
        await session.execute(
            update(AuthSocialAccountModel)
            .where(
                AuthSocialAccountModel.user_id == user_id,
                AuthSocialAccountModel.provider == provider,
                AuthSocialAccountModel.provider_user_id == provider_user_id,
            )
            .values(last_login_at=now, updated_at=now)
        )

        return True

    # =========================================================================
    # Private Methods - Protobuf Conversion
    # =========================================================================

    def _user_to_proto(self, user: AuthUserModel) -> users_pb2.UserInfo:
        """AuthUserModel → UserInfo protobuf."""
        return users_pb2.UserInfo(
            id=str(user.id),
            username=user.username or "",
            nickname=user.nickname or "",
            profile_image_url=user.profile_image_url or "",
            phone_number=user.phone_number or "",
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else "",
        )

    def _social_account_to_proto(
        self, account: AuthSocialAccountModel
    ) -> users_pb2.SocialAccountInfo:
        """AuthSocialAccountModel → SocialAccountInfo protobuf."""
        return users_pb2.SocialAccountInfo(
            id=str(account.id),
            user_id=str(account.user_id),
            provider=account.provider,
            provider_user_id=account.provider_user_id,
            email=account.email or "",
            created_at=account.created_at.isoformat() if account.created_at else "",
            last_login_at=account.last_login_at.isoformat() if account.last_login_at else "",
        )
