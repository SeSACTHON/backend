"""OAuthAuthorizeInteractor 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from apps.auth.application.commands.oauth_authorize import OAuthAuthorizeInteractor
from apps.auth.application.common.dto.auth import OAuthAuthorizeRequest
from apps.auth.application.common.ports.state_store import OAuthState


class TestOAuthAuthorizeInteractor:
    """OAuthAuthorizeInteractor 테스트."""

    @pytest.fixture
    def mock_state_store(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_oauth_client(self) -> MagicMock:
        client = MagicMock()
        client.get_authorization_url.return_value = "https://accounts.google.com/oauth?..."
        return client

    @pytest.fixture
    def interactor(
        self,
        mock_state_store: AsyncMock,
        mock_oauth_client: MagicMock,
    ) -> OAuthAuthorizeInteractor:
        return OAuthAuthorizeInteractor(
            state_store=mock_state_store,
            oauth_client=mock_oauth_client,
        )

    @pytest.mark.asyncio
    async def test_execute_creates_state_and_returns_url(
        self,
        interactor: OAuthAuthorizeInteractor,
        mock_state_store: AsyncMock,
        mock_oauth_client: MagicMock,
    ) -> None:
        """인증 URL 생성 및 state 저장 테스트."""
        # Arrange
        request = OAuthAuthorizeRequest(
            provider="google",
            redirect_uri="http://localhost:8000/callback",
            frontend_origin="http://localhost:3000",
        )

        # Act
        result = await interactor.execute(request)

        # Assert
        assert result.authorization_url == "https://accounts.google.com/oauth?..."
        assert result.state is not None
        assert len(result.state) > 20  # state는 충분히 긴 랜덤 문자열

        # state_store.save가 호출되었는지 확인
        mock_state_store.save.assert_called_once()
        call_args = mock_state_store.save.call_args
        saved_state = call_args[0][0]
        saved_oauth_state: OAuthState = call_args[0][1]

        assert saved_state == result.state
        assert saved_oauth_state.provider == "google"
        assert saved_oauth_state.redirect_uri == "http://localhost:8000/callback"
        assert saved_oauth_state.frontend_origin == "http://localhost:3000"
        assert saved_oauth_state.code_verifier is not None  # PKCE

    @pytest.mark.asyncio
    async def test_execute_with_custom_state(
        self,
        interactor: OAuthAuthorizeInteractor,
        mock_state_store: AsyncMock,
    ) -> None:
        """커스텀 state 사용 테스트."""
        # Arrange
        custom_state = "my-custom-state-12345"
        request = OAuthAuthorizeRequest(
            provider="kakao",
            state=custom_state,
        )

        # Act
        result = await interactor.execute(request)

        # Assert
        assert result.state == custom_state

    @pytest.mark.asyncio
    async def test_execute_with_device_id(
        self,
        interactor: OAuthAuthorizeInteractor,
        mock_state_store: AsyncMock,
    ) -> None:
        """device_id 저장 테스트."""
        # Arrange
        request = OAuthAuthorizeRequest(
            provider="naver",
            device_id="device-abc-123",
        )

        # Act
        await interactor.execute(request)

        # Assert
        call_args = mock_state_store.save.call_args
        saved_oauth_state: OAuthState = call_args[0][1]
        assert saved_oauth_state.device_id == "device-abc-123"

    @pytest.mark.asyncio
    async def test_execute_calls_oauth_client_with_correct_params(
        self,
        interactor: OAuthAuthorizeInteractor,
        mock_oauth_client: MagicMock,
    ) -> None:
        """OAuth 클라이언트에 올바른 파라미터 전달 테스트."""
        # Arrange
        request = OAuthAuthorizeRequest(
            provider="google",
            redirect_uri="http://localhost:8000/callback",
        )

        # Act
        result = await interactor.execute(request)

        # Assert
        mock_oauth_client.get_authorization_url.assert_called_once()
        call_kwargs = mock_oauth_client.get_authorization_url.call_args[1]

        assert call_kwargs["redirect_uri"] == "http://localhost:8000/callback"
        assert call_kwargs["state"] == result.state
        assert "code_verifier" in call_kwargs
