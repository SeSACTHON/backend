"""OAuthCallback Command.

OAuth 콜백 처리 Use Case입니다.

Phase 1: gRPC를 통해 users 도메인과 통신합니다.
- UserManagementService 포트를 통해 사용자 조회/생성
- 기존 UserService, UserCommandGateway 등은 deprecated

참고: https://rooftopsnow.tistory.com/127
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from apps.auth.domain.entities.login_audit import LoginAudit
from apps.auth.application.common.dto.auth import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
)
from apps.auth.application.common.exceptions.auth import (
    InvalidStateError,
    OAuthProviderError,
    UserServiceUnavailableError,
)
from apps.auth.application.common.ports.login_audit_gateway import LoginAuditGateway
from apps.auth.application.common.ports.token_service import TokenService
from apps.auth.application.common.ports.state_store import StateStore
from apps.auth.application.common.ports.user_token_store import UserTokenStore
from apps.auth.application.common.ports.flusher import Flusher
from apps.auth.application.common.ports.transaction_manager import TransactionManager
from apps.auth.application.common.ports.user_management_service import (
    UserManagementService,
)
from apps.auth.application.common.services.oauth_client import OAuthClientService

logger = logging.getLogger(__name__)


class OAuthCallbackInteractor:
    """OAuth 콜백 Interactor.

    OAuth 로그인 플로우의 콜백 단계:
    1. state 검증
    2. OAuth 토큰 교환 및 프로필 조회
    3. 사용자 조회 또는 생성 (via gRPC to users domain)
    4. JWT 토큰 발급
    5. 토큰 저장 및 감사 기록
    6. 커밋
    """

    def __init__(
        self,
        user_management: UserManagementService,
        login_audit_gateway: LoginAuditGateway,
        token_service: TokenService,
        state_store: StateStore,
        user_token_store: UserTokenStore,
        oauth_client: OAuthClientService,
        flusher: Flusher,
        transaction_manager: TransactionManager,
    ) -> None:
        self._user_management = user_management
        self._login_audit_gateway = login_audit_gateway
        self._token_service = token_service
        self._state_store = state_store
        self._user_token_store = user_token_store
        self._oauth_client = oauth_client
        self._flusher = flusher
        self._transaction_manager = transaction_manager

    async def execute(self, request: OAuthCallbackRequest) -> OAuthCallbackResponse:
        """OAuth 콜백 처리.

        Args:
            request: 콜백 요청 DTO

        Returns:
            로그인 결과 응답 DTO

        Raises:
            InvalidStateError: 상태 검증 실패
            OAuthProviderError: OAuth 프로바이더 오류
            UserServiceUnavailableError: users 도메인 통신 실패
        """
        # 1. state 검증
        state_data = await self._state_store.consume(request.state)
        if not state_data:
            raise InvalidStateError("Invalid or expired state")
        if state_data.provider != request.provider:
            raise InvalidStateError("State provider mismatch")

        # 2. OAuth 프로필 조회
        redirect_uri = request.redirect_uri or state_data.redirect_uri or ""
        try:
            profile = await self._oauth_client.fetch_profile(
                request.provider,
                code=request.code,
                redirect_uri=redirect_uri,
                state=request.state,
                code_verifier=state_data.code_verifier,
            )
        except Exception as e:
            logger.warning(f"OAuth profile fetch failed: {e}")
            raise OAuthProviderError(request.provider, str(e)) from e

        # 3. 사용자 조회 또는 생성 (via gRPC to users domain)
        user_result = await self._user_management.get_or_create_from_oauth(
            provider=profile.provider,
            provider_user_id=profile.provider_user_id,
            email=profile.email,
            nickname=profile.nickname,
            profile_image_url=profile.profile_image_url,
        )

        if user_result is None:
            logger.error(
                "Failed to get/create user via users service",
                extra={
                    "provider": profile.provider,
                    "provider_user_id": profile.provider_user_id,
                },
            )
            raise UserServiceUnavailableError("Could not communicate with users service")

        user_id = user_result.user_id

        # 4. JWT 토큰 발급
        token_pair = self._token_service.issue_pair(
            user_id=user_id,
            provider=request.provider,
        )

        # 5. 토큰 저장
        await self._user_token_store.register(
            user_id=user_id,
            jti=token_pair.refresh_jti,
            issued_at=token_pair.access_expires_at - 900,  # 대략적인 발급 시간
            expires_at=token_pair.refresh_expires_at,
            device_id=state_data.device_id,
            user_agent=request.user_agent,
        )

        # 6. 로그인 감사 기록
        login_audit = LoginAudit(
            id=uuid4(),
            user_id=user_id,
            provider=request.provider,
            jti=token_pair.access_jti,
            login_ip=request.ip_address,
            user_agent=request.user_agent,
            issued_at=datetime.now(timezone.utc),
        )
        self._login_audit_gateway.add(login_audit)

        # 7. 커밋
        await self._flusher.flush()
        await self._transaction_manager.commit()

        logger.info(
            "OAuth login successful",
            extra={
                "user_id": str(user_id),
                "provider": request.provider,
                "is_new_user": user_result.is_new_user,
            },
        )

        return OAuthCallbackResponse(
            user_id=user_id,
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            access_expires_at=token_pair.access_expires_at,
            refresh_expires_at=token_pair.refresh_expires_at,
            frontend_origin=state_data.frontend_origin,
        )
