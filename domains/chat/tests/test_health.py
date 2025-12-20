"""Health 엔드포인트 테스트"""

import httpx
import pytest
import pytest_asyncio

from domains.chat.main import app


@pytest_asyncio.fixture
async def client() -> httpx.AsyncClient:
    """비동기 테스트 클라이언트 fixture"""
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestHealthEndpoints:
    """Health/Readiness 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: httpx.AsyncClient) -> None:
        """GET /health가 200 반환"""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_format(self, client: httpx.AsyncClient) -> None:
        """GET /health 응답 형식"""
        from domains.chat.core.constants import SERVICE_NAME

        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == SERVICE_NAME

    @pytest.mark.asyncio
    async def test_readiness_returns_200(self, client: httpx.AsyncClient) -> None:
        """GET /ready가 200 반환"""
        response = await client.get("/ready")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_response_format(self, client: httpx.AsyncClient) -> None:
        """GET /ready 응답 형식"""
        from domains.chat.core.constants import SERVICE_NAME

        response = await client.get("/ready")
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == SERVICE_NAME
