"""Pytest configuration for Character domain tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None  # pytest-asyncio not installed

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add extra path for shared modules
extra_path = project_root / "domains"
if str(extra_path) not in sys.path:
    sys.path.insert(0, str(extra_path))

# Disable tracing for tests
os.environ["OTEL_ENABLED"] = "false"
os.environ["AUTH_DISABLED"] = "true"


# ============================================================================
# Test Fixtures for Unit Tests
# ============================================================================


@pytest.fixture
def mock_character():
    """Factory fixture for creating mock characters."""

    def _create(
        name: str = "테스트캐릭터",
        type_label: str = "테스트",
        match_label: str = "플라스틱",
        dialog: str = "안녕!",
    ):
        char = MagicMock()
        char.id = uuid4()
        char.name = name
        char.type_label = type_label
        char.match_label = match_label
        char.dialog = dialog
        char.description = None
        char.code = f"{name.upper()[:4]}001"
        return char

    return _create


@pytest.fixture
def test_user_id() -> UUID:
    """Test user ID fixture."""
    return UUID("12345678-1234-5678-1234-567812345678")


# ============================================================================
# E2E Test Fixtures (API Integration)
# ============================================================================

# Conditionally define async fixtures if pytest_asyncio is available
if pytest_asyncio is not None:

    @pytest_asyncio.fixture
    async def app():
        """Create FastAPI app for E2E testing with mocked dependencies."""
        from domains.character.main import create_app

        test_app = create_app()
        yield test_app

    @pytest_asyncio.fixture
    async def async_client(app):
        """Async HTTP client for E2E tests."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    @pytest_asyncio.fixture
    async def mock_db_session_e2e():
        """Mock DB session for E2E tests."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest_asyncio.fixture
    async def mock_character_service(mock_character):
        """Mock CharacterService for E2E tests."""
        from domains.character.schemas.catalog import CharacterProfile
        from domains.character.schemas.reward import CharacterRewardResponse

        service = AsyncMock()

        # Default catalog response
        char = mock_character(name="이코", type_label="기본", match_label="플라스틱")
        service.catalog.return_value = [
            CharacterProfile(
                name=char.name,
                type=char.type_label,
                dialog=char.dialog,
                match=char.match_label,
            )
        ]

        # Default reward response
        service.evaluate_reward.return_value = CharacterRewardResponse(
            received=True,
            already_owned=False,
            name="플라봇",
            dialog="플라스틱을 분리해줘서 고마워!",
            match_reason="플라스틱>페트병",
            character_type="플라스틱",
            type="플라스틱",
        )

        return service


# ============================================================================
# E2E Test Helpers
# ============================================================================


def create_reward_request_payload(
    user_id: UUID | None = None,
    major_category: str = "재활용폐기물",
    middle_category: str = "플라스틱",
    minor_category: str | None = "페트병",
    disposal_rules_present: bool = True,
    insufficiencies_present: bool = False,
) -> dict:
    """Helper to create reward request payloads for testing."""
    return {
        "source": "scan",
        "user_id": str(user_id or uuid4()),
        "task_id": f"test-task-{uuid4().hex[:8]}",
        "classification": {
            "major_category": major_category,
            "middle_category": middle_category,
            "minor_category": minor_category,
        },
        "disposal_rules_present": disposal_rules_present,
        "insufficiencies_present": insufficiencies_present,
    }
