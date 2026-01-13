"""IntentClassifier 단위 테스트.

Port Mock으로 Service 독립 테스트.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from chat_worker.application.intent.services.intent_classifier import (
    COMPLEX_KEYWORDS,
    IntentClassifier,
)
from chat_worker.application.ports.llm import LLMClientPort
from chat_worker.domain import Intent, QueryComplexity


class MockLLMClient(LLMClientPort):
    """테스트용 LLM Mock."""

    def __init__(self, response: str = "general"):
        self._response = response
        self.generate_called = False
        self.last_prompt: str | None = None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        self.generate_called = True
        self.last_prompt = prompt
        return self._response

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        yield self._response


class TestIntentClassifier:
    """IntentClassifier 테스트 스위트."""

    @pytest.fixture
    def mock_llm(self) -> MockLLMClient:
        """기본 Mock LLM."""
        return MockLLMClient("general")

    @pytest.fixture
    def classifier(self, mock_llm: MockLLMClient) -> IntentClassifier:
        """테스트용 IntentClassifier."""
        return IntentClassifier(mock_llm)

    # ==========================================================
    # Intent Classification Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_classify_waste_intent(self):
        """waste 의도 분류."""
        mock_llm = MockLLMClient("waste")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("페트병 어떻게 버려?")

        assert result.intent == Intent.WASTE
        assert result.confidence == 1.0
        assert mock_llm.generate_called

    @pytest.mark.asyncio
    async def test_classify_character_intent(self):
        """character 의도 분류."""
        mock_llm = MockLLMClient("character")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("플라스틱 캐릭터 뭐야?")

        assert result.intent == Intent.CHARACTER

    @pytest.mark.asyncio
    async def test_classify_location_intent(self):
        """location 의도 분류."""
        mock_llm = MockLLMClient("location")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("근처 재활용 센터 알려줘")

        assert result.intent == Intent.LOCATION

    @pytest.mark.asyncio
    async def test_classify_general_intent(self):
        """general 의도 분류."""
        mock_llm = MockLLMClient("general")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("안녕하세요")

        assert result.intent == Intent.GENERAL

    @pytest.mark.asyncio
    async def test_classify_unknown_fallback_to_general(self):
        """알 수 없는 응답은 general로."""
        mock_llm = MockLLMClient("unknown_intent_xyz")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("아무거나")

        assert result.intent == Intent.GENERAL

    @pytest.mark.asyncio
    async def test_classify_strips_whitespace(self):
        """응답 공백 제거."""
        mock_llm = MockLLMClient("  waste  \n")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("페트병")

        assert result.intent == Intent.WASTE

    @pytest.mark.asyncio
    async def test_classify_case_insensitive(self):
        """대소문자 무관."""
        mock_llm = MockLLMClient("WASTE")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("페트병")

        assert result.intent == Intent.WASTE

    # ==========================================================
    # Complexity Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_simple_query_complexity(self):
        """단순 쿼리 복잡도."""
        mock_llm = MockLLMClient("waste")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("페트병 버리기")

        assert result.complexity == QueryComplexity.SIMPLE
        assert not result.needs_subagent

    @pytest.mark.asyncio
    async def test_complex_query_with_keyword(self):
        """복잡도 키워드 감지."""
        mock_llm = MockLLMClient("waste")
        classifier = IntentClassifier(mock_llm)

        # COMPLEX_KEYWORDS에 있는 키워드 사용
        result = await classifier.classify("페트병 그리고 유리병 어떻게 버려?")

        # COMPLEX
        assert result.complexity == QueryComplexity.COMPLEX

    @pytest.mark.asyncio
    async def test_complex_query_long_message(self):
        """긴 메시지는 복잡한 쿼리로."""
        mock_llm = MockLLMClient("general")
        classifier = IntentClassifier(mock_llm)

        long_message = "a" * 101  # 100자 초과

        result = await classifier.classify(long_message)

        assert result.complexity == QueryComplexity.COMPLEX

    @pytest.mark.asyncio
    async def test_all_complex_keywords(self):
        """모든 복잡도 키워드 테스트."""
        mock_llm = MockLLMClient("general")
        classifier = IntentClassifier(mock_llm)

        for keyword in COMPLEX_KEYWORDS:
            message = f"테스트 {keyword} 메시지"
            result = await classifier.classify(message)
            assert result.complexity == QueryComplexity.COMPLEX, f"Keyword '{keyword}' should trigger complex"

    # ==========================================================
    # Error Handling Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_llm_error_fallback(self):
        """LLM 오류 시 기본값."""
        mock_llm = AsyncMock(spec=LLMClientPort)
        mock_llm.generate.side_effect = Exception("API Error")
        classifier = IntentClassifier(mock_llm)

        result = await classifier.classify("테스트")

        assert result.intent == Intent.GENERAL
        assert result.confidence == 0.0

    # ==========================================================
    # Integration-like Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_prompt_passed_correctly(self):
        """프롬프트가 올바르게 전달되는지."""
        mock_llm = MockLLMClient("waste")
        classifier = IntentClassifier(mock_llm)

        await classifier.classify("테스트 메시지")

        assert mock_llm.last_prompt == "테스트 메시지"
