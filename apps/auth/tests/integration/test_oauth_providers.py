"""OAuth Provider Integration Tests.

실제 OAuth 프로바이더와의 통합 테스트는 CI에서 skip됩니다.
로컬에서 실행 시: pytest -m integration --oauth-test
"""

from __future__ import annotations

import pytest

from auth.infrastructure.oauth import (
    GoogleOAuthProvider,
    KakaoOAuthProvider,
    NaverOAuthProvider,
)


class TestGoogleOAuthProvider:
    """Google OAuth 프로바이더 테스트."""

    @pytest.fixture
    def provider(self) -> GoogleOAuthProvider:
        return GoogleOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback",
        )

    def test_build_authorization_url(self, provider: GoogleOAuthProvider) -> None:
        """인증 URL 생성 테스트."""
        # Act
        url = provider.build_authorization_url(
            state="test-state",
            code_challenge="test-challenge",
            scope=None,
            redirect_uri=None,
        )

        # Assert
        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "state=test-state" in url
        assert "code_challenge=test-challenge" in url

    def test_default_scopes(self, provider: GoogleOAuthProvider) -> None:
        """기본 스코프 확인."""
        assert "openid" in provider.default_scopes
        assert "email" in provider.default_scopes
        assert "profile" in provider.default_scopes


class TestKakaoOAuthProvider:
    """Kakao OAuth 프로바이더 테스트."""

    @pytest.fixture
    def provider(self) -> KakaoOAuthProvider:
        return KakaoOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback",
        )

    def test_build_authorization_url(self, provider: KakaoOAuthProvider) -> None:
        """인증 URL 생성 테스트."""
        # Act
        url = provider.build_authorization_url(
            state="test-state",
            code_challenge=None,
            scope=None,
            redirect_uri=None,
        )

        # Assert
        assert "kauth.kakao.com" in url
        assert "client_id=test-client-id" in url
        assert "state=test-state" in url

    def test_default_scopes_empty(self, provider: KakaoOAuthProvider) -> None:
        """카카오는 빈 스코프 (개발자 콘솔에서 설정)."""
        assert provider.default_scopes == ()


class TestNaverOAuthProvider:
    """Naver OAuth 프로바이더 테스트."""

    @pytest.fixture
    def provider(self) -> NaverOAuthProvider:
        return NaverOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback",
        )

    def test_build_authorization_url(self, provider: NaverOAuthProvider) -> None:
        """인증 URL 생성 테스트."""
        # Act
        url = provider.build_authorization_url(
            state="test-state",
            code_challenge=None,
            scope=None,
            redirect_uri=None,
        )

        # Assert
        assert "nid.naver.com" in url
        assert "client_id=test-client-id" in url
        assert "state=test-state" in url

    def test_pkce_not_supported(self, provider: NaverOAuthProvider) -> None:
        """네이버는 PKCE 미지원."""
        assert provider.supports_pkce is False
