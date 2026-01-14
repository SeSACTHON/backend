"""PromptBuilder 단위 테스트.

Local Prompt Optimization 시스템 테스트 (arxiv:2504.20355):
- Global + Local 조합 검증
- Intent 정규화 검증
- 캐싱 동작 검증
"""

import pytest

from chat_worker.infrastructure.orchestration.prompts.loader import (
    PromptBuilder,
    get_prompt_builder,
    load_prompt_file,
)


class TestPromptBuilder:
    """PromptBuilder 클래스 테스트."""

    @pytest.fixture
    def builder(self) -> PromptBuilder:
        """PromptBuilder 인스턴스."""
        return PromptBuilder()

    def test_init_loads_all_prompts(self, builder: PromptBuilder):
        """초기화 시 모든 프롬프트가 로드되는지 확인."""
        # Global 프롬프트 로드 확인
        assert builder.global_prompt is not None
        assert len(builder.global_prompt) > 0
        assert "이코" in builder.global_prompt

        # Local 프롬프트 로드 확인
        assert builder.get_local_prompt("waste") is not None
        assert builder.get_local_prompt("character") is not None
        assert builder.get_local_prompt("location") is not None
        assert builder.get_local_prompt("general") is not None

    def test_build_waste_prompt(self, builder: PromptBuilder):
        """waste Intent 프롬프트 빌드 테스트."""
        prompt = builder.build("waste")

        # Global + Local 조합 확인
        assert "이코" in prompt  # Global
        assert "disposal_rules" in prompt or "RAG" in prompt  # Local waste

    def test_build_character_prompt(self, builder: PromptBuilder):
        """character Intent 프롬프트 빌드 테스트."""
        prompt = builder.build("character")

        # Global + Local 조합 확인
        assert "이코" in prompt  # Global
        assert "character" in prompt.lower()  # Local character

    def test_build_location_prompt(self, builder: PromptBuilder):
        """location Intent 프롬프트 빌드 테스트."""
        prompt = builder.build("location")

        # Global + Local 조합 확인
        assert "이코" in prompt  # Global
        assert "location" in prompt.lower() or "위치" in prompt  # Local location

    def test_build_general_prompt(self, builder: PromptBuilder):
        """general Intent 프롬프트 빌드 테스트."""
        prompt = builder.build("general")

        # Global + Local 조합 확인
        assert "이코" in prompt  # Global
        assert len(prompt) > len(builder.global_prompt)  # Local 추가됨

    def test_build_unknown_intent_fallback(self, builder: PromptBuilder):
        """알 수 없는 Intent는 general로 fallback."""
        prompt = builder.build("unknown_intent")
        general_prompt = builder.build("general")

        # unknown -> general fallback
        assert prompt == general_prompt

    def test_normalize_intent_variations(self, builder: PromptBuilder):
        """Intent 변형들이 올바르게 정규화되는지 확인."""
        # waste 변형
        assert builder._normalize_intent("waste") == "waste"
        assert builder._normalize_intent("waste_query") == "waste"
        assert builder._normalize_intent("recycling") == "waste"
        assert builder._normalize_intent("disposal") == "waste"

        # character 변형
        assert builder._normalize_intent("character") == "character"
        assert builder._normalize_intent("character_query") == "character"
        assert builder._normalize_intent("my_character") == "character"

        # location 변형
        assert builder._normalize_intent("location") == "location"
        assert builder._normalize_intent("location_query") == "location"
        assert builder._normalize_intent("zerowaste") == "location"

        # general 변형
        assert builder._normalize_intent("general") == "general"
        assert builder._normalize_intent("greeting") == "general"
        assert builder._normalize_intent("unknown") == "general"

    def test_normalize_intent_case_insensitive(self, builder: PromptBuilder):
        """Intent 정규화가 대소문자를 무시하는지 확인."""
        assert builder._normalize_intent("WASTE") == "waste"
        assert builder._normalize_intent("Waste") == "waste"
        assert builder._normalize_intent("CHARACTER") == "character"

    def test_prompt_contains_separator(self, builder: PromptBuilder):
        """Global과 Local 사이에 구분자가 있는지 확인."""
        prompt = builder.build("waste")
        assert "---" in prompt

    def test_prompt_structure(self, builder: PromptBuilder):
        """프롬프트 구조가 올바른지 확인."""
        prompt = builder.build("waste")

        # Global이 먼저 나오고 Local이 뒤에
        global_start = prompt.find("이코")
        local_marker = prompt.find("---")

        assert global_start < local_marker


class TestLoadPromptFile:
    """load_prompt_file 함수 테스트."""

    def test_load_global_prompt(self):
        """Global 프롬프트 파일 로드."""
        content = load_prompt_file("global", "eco_character")
        assert "이코" in content

    def test_load_local_waste_prompt(self):
        """Local waste 프롬프트 파일 로드."""
        content = load_prompt_file("local", "waste_instruction")
        assert len(content) > 0

    def test_load_nonexistent_file_raises(self):
        """존재하지 않는 파일 로드 시 예외 발생."""
        with pytest.raises(FileNotFoundError):
            load_prompt_file("global", "nonexistent_file")


class TestGetPromptBuilder:
    """get_prompt_builder 싱글톤 테스트."""

    def test_returns_same_instance(self):
        """싱글톤이 동일한 인스턴스를 반환하는지 확인."""
        builder1 = get_prompt_builder()
        builder2 = get_prompt_builder()

        assert builder1 is builder2

    def test_returns_prompt_builder_instance(self):
        """반환 타입이 PromptBuilder인지 확인."""
        builder = get_prompt_builder()
        assert isinstance(builder, PromptBuilder)
