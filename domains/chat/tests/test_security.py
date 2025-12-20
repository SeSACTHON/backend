"""Security 모듈 테스트

인증 헤더 추출 및 검증
"""

from uuid import UUID

import pytest
from fastapi import HTTPException

from domains.chat.security import UserInfo, _extract_user_info


class TestUserInfo:
    """UserInfo 모델 테스트"""

    def test_valid_user_info(self) -> None:
        """유효한 UserInfo 생성"""
        user = UserInfo(
            user_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            provider="google",
        )
        assert str(user.user_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert user.provider == "google"

    def test_frozen_model(self) -> None:
        """UserInfo는 immutable (Pydantic frozen 설정)"""
        user = UserInfo(
            user_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            provider="google",
        )
        # frozen 모델은 hash 가능해야 함
        assert hash(user) is not None


class TestExtractUserInfo:
    """_extract_user_info 함수 테스트"""

    @pytest.mark.asyncio
    async def test_valid_headers(self) -> None:
        """유효한 헤더로 UserInfo 추출"""
        result = await _extract_user_info(
            x_user_id="550e8400-e29b-41d4-a716-446655440000",
            x_auth_provider="kakao",
        )
        assert str(result.user_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert result.provider == "kakao"

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_401(self) -> None:
        """x-user-id 누락 시 401 에러"""
        with pytest.raises(HTTPException) as exc_info:
            await _extract_user_info(x_user_id=None, x_auth_provider="google")

        assert exc_info.value.status_code == 401
        assert "Missing x-user-id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_user_id_raises_401(self) -> None:
        """x-user-id 빈 문자열 시 401 에러"""
        with pytest.raises(HTTPException) as exc_info:
            await _extract_user_info(x_user_id="", x_auth_provider="google")

        assert exc_info.value.status_code == 401
        assert "Missing x-user-id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_uuid_format_raises_401(self) -> None:
        """잘못된 UUID 형식 시 401 에러"""
        with pytest.raises(HTTPException) as exc_info:
            await _extract_user_info(
                x_user_id="not-a-valid-uuid",
                x_auth_provider="google",
            )

        assert exc_info.value.status_code == 401
        assert "Invalid x-user-id format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_provider_defaults_to_unknown(self) -> None:
        """x-auth-provider 누락 시 'unknown' 기본값"""
        result = await _extract_user_info(
            x_user_id="550e8400-e29b-41d4-a716-446655440000",
            x_auth_provider=None,
        )
        assert result.provider == "unknown"

    @pytest.mark.asyncio
    async def test_empty_provider_defaults_to_unknown(self) -> None:
        """x-auth-provider 빈 문자열 시 'unknown'"""
        result = await _extract_user_info(
            x_user_id="550e8400-e29b-41d4-a716-446655440000",
            x_auth_provider="",
        )
        # 빈 문자열은 falsy이므로 "unknown"으로 대체됨
        assert result.provider == "unknown"
