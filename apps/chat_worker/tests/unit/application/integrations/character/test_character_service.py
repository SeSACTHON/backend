"""CharacterService 단위 테스트."""

from __future__ import annotations

import pytest

from chat_worker.application.integrations.character.ports import (
    CharacterClientPort,
    CharacterDTO,
)
from chat_worker.application.integrations.character.services.character_service import (
    CharacterService,
)


class MockCharacterClient(CharacterClientPort):
    """테스트용 Character Mock."""

    def __init__(self, characters: dict[str, CharacterDTO] | None = None):
        self._characters = characters or {}
        self._catalog: list[CharacterDTO] = []
        self.get_by_category_called = False
        self.last_category: str | None = None

    async def get_character_by_waste_category(
        self,
        waste_category: str,
    ) -> CharacterDTO | None:
        self.get_by_category_called = True
        self.last_category = waste_category
        return self._characters.get(waste_category)

    async def get_catalog(self) -> list[CharacterDTO]:
        return self._catalog


class TestCharacterService:
    """CharacterService 테스트 스위트."""

    @pytest.fixture
    def sample_character(self) -> CharacterDTO:
        """샘플 캐릭터."""
        return CharacterDTO(
            name="페트리",
            type_label="재활용",
            dialog="재활용해줘서 고마워!",
            match_label="플라스틱",
        )

    @pytest.fixture
    def mock_client(self, sample_character: CharacterDTO) -> MockCharacterClient:
        """Mock 클라이언트."""
        return MockCharacterClient(
            characters={"플라스틱": sample_character},
        )

    @pytest.fixture
    def service(self, mock_client: MockCharacterClient) -> CharacterService:
        """테스트용 서비스."""
        return CharacterService(mock_client)

    # ==========================================================
    # find_by_waste_category Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_find_by_waste_category_found(
        self,
        service: CharacterService,
        mock_client: MockCharacterClient,
        sample_character: CharacterDTO,
    ):
        """캐릭터 검색 성공."""
        result = await service.find_by_waste_category("플라스틱")

        assert result is not None
        assert result.name == sample_character.name
        assert result.dialog == sample_character.dialog
        assert mock_client.get_by_category_called
        assert mock_client.last_category == "플라스틱"

    @pytest.mark.asyncio
    async def test_find_by_waste_category_not_found(
        self,
        service: CharacterService,
    ):
        """캐릭터 검색 실패."""
        result = await service.find_by_waste_category("존재하지않는카테고리")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_waste_category_passes_category(
        self,
        service: CharacterService,
        mock_client: MockCharacterClient,
    ):
        """카테고리가 올바르게 전달되는지."""
        await service.find_by_waste_category("종이류")

        assert mock_client.last_category == "종이류"

    # ==========================================================
    # get_all Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_get_all_empty(
        self,
        service: CharacterService,
    ):
        """빈 카탈로그."""
        result = await service.get_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_with_characters(
        self,
        sample_character: CharacterDTO,
    ):
        """캐릭터 목록 조회."""
        mock_client = MockCharacterClient()
        mock_client._catalog = [
            sample_character,
            CharacterDTO(
                name="글래시",
                type_label="재활용",
                dialog="유리도 재활용!",
                match_label="유리",
            ),
        ]
        service = CharacterService(mock_client)

        result = await service.get_all()

        assert len(result) == 2
        assert result[0].name == "페트리"
        assert result[1].name == "글래시"

    # ==========================================================
    # to_answer_context Tests
    # ==========================================================

    def test_to_answer_context(self, sample_character: CharacterDTO):
        """컨텍스트 변환."""
        context = CharacterService.to_answer_context(sample_character)

        assert context["name"] == "페트리"
        assert context["type"] == "재활용"
        assert context["dialog"] == "재활용해줘서 고마워!"
        assert context["match_reason"] == "플라스틱"

    def test_to_answer_context_with_none_match_label(self):
        """match_label이 None인 경우."""
        character = CharacterDTO(
            name="테스트",
            type_label="타입",
            dialog="대사",
            match_label=None,
        )

        context = CharacterService.to_answer_context(character)

        assert context["match_reason"] is None

    def test_to_answer_context_structure(self, sample_character: CharacterDTO):
        """컨텍스트 구조 확인."""
        context = CharacterService.to_answer_context(sample_character)

        expected_keys = {"name", "type", "dialog", "match_reason"}
        assert set(context.keys()) == expected_keys
