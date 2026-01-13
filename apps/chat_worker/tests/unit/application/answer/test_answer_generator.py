"""AnswerGeneratorService 단위 테스트."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from chat_worker.application.answer.dto import AnswerContext
from chat_worker.application.answer.services.answer_generator import (
    AnswerGeneratorService,
)
from chat_worker.application.ports.llm import LLMClientPort


class MockLLMClient(LLMClientPort):
    """테스트용 LLM Mock."""

    def __init__(self, response: str = "테스트 답변입니다."):
        self._response = response
        self.generate_called = False
        self.generate_stream_called = False
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None

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
        self.last_system_prompt = system_prompt
        return self._response

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        self.generate_stream_called = True
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        for word in self._response.split():
            yield word + " "


class TestAnswerGeneratorService:
    """AnswerGeneratorService 테스트 스위트."""

    @pytest.fixture
    def mock_llm(self) -> MockLLMClient:
        """기본 Mock LLM."""
        return MockLLMClient("페트병은 라벨을 제거하고 재활용 분리수거함에 버려주세요.")

    @pytest.fixture
    def service(self, mock_llm: MockLLMClient) -> AnswerGeneratorService:
        """테스트용 서비스."""
        return AnswerGeneratorService(mock_llm)

    @pytest.fixture
    def simple_context(self) -> AnswerContext:
        """간단한 컨텍스트."""
        return AnswerContext(
            user_input="페트병 어떻게 버려?",
        )

    @pytest.fixture
    def full_context(self) -> AnswerContext:
        """전체 컨텍스트."""
        return AnswerContext(
            classification={"major_category": "재활용", "minor_category": "페트병"},
            disposal_rules={"method": "라벨 제거 후 분리수거"},
            character_context={"name": "페트리", "dialog": "재활용해줘서 고마워!"},
            location_context={"found": True, "count": 3},
            user_input="페트병 어떻게 버려?",
        )

    # ==========================================================
    # Generate Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_generate_simple(
        self,
        service: AnswerGeneratorService,
        mock_llm: MockLLMClient,
        simple_context: AnswerContext,
    ):
        """간단한 답변 생성."""
        system_prompt = "당신은 분리배출 도우미입니다."

        answer = await service.generate(simple_context, system_prompt)

        assert mock_llm.generate_called
        assert mock_llm.last_system_prompt == system_prompt
        assert len(answer) > 0

    @pytest.mark.asyncio
    async def test_generate_with_full_context(
        self,
        service: AnswerGeneratorService,
        mock_llm: MockLLMClient,
        full_context: AnswerContext,
    ):
        """전체 컨텍스트로 답변 생성."""
        system_prompt = "당신은 분리배출 도우미입니다."

        answer = await service.generate(full_context, system_prompt)

        assert mock_llm.generate_called
        # 컨텍스트가 프롬프트에 포함되었는지 확인
        assert "페트병" in mock_llm.last_prompt or "재활용" in mock_llm.last_prompt

    @pytest.mark.asyncio
    async def test_generate_prompt_contains_user_input(
        self,
        service: AnswerGeneratorService,
        mock_llm: MockLLMClient,
        simple_context: AnswerContext,
    ):
        """프롬프트에 사용자 입력 포함."""
        await service.generate(simple_context, "시스템 프롬프트")

        assert "페트병" in mock_llm.last_prompt

    # ==========================================================
    # Generate Stream Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_generate_stream(
        self,
        service: AnswerGeneratorService,
        mock_llm: MockLLMClient,
        simple_context: AnswerContext,
    ):
        """스트리밍 답변 생성."""
        system_prompt = "당신은 분리배출 도우미입니다."
        chunks = []

        async for chunk in service.generate_stream(simple_context, system_prompt):
            chunks.append(chunk)

        assert mock_llm.generate_stream_called
        assert len(chunks) > 0
        assert "".join(chunks).strip()  # 빈 문자열이 아님

    @pytest.mark.asyncio
    async def test_generate_stream_with_full_context(
        self,
        service: AnswerGeneratorService,
        mock_llm: MockLLMClient,
        full_context: AnswerContext,
    ):
        """전체 컨텍스트로 스트리밍."""
        chunks = []
        async for chunk in service.generate_stream(full_context, "시스템"):
            chunks.append(chunk)

        assert mock_llm.generate_stream_called
        assert len(chunks) > 0

    # ==========================================================
    # Factory Method Tests
    # ==========================================================

    def test_create_context_minimal(self):
        """최소 컨텍스트 생성."""
        context = AnswerGeneratorService.create_context(
            user_input="테스트",
        )

        assert context.user_input == "테스트"
        assert context.classification is None
        assert context.disposal_rules is None

    def test_create_context_full(self):
        """전체 컨텍스트 생성."""
        context = AnswerGeneratorService.create_context(
            classification={"key": "value"},
            disposal_rules={"rule": "test"},
            character_context={"name": "테스트"},
            location_context={"found": True},
            user_input="테스트 질문",
        )

        assert context.classification == {"key": "value"}
        assert context.disposal_rules == {"rule": "test"}
        assert context.character_context == {"name": "테스트"}
        assert context.location_context == {"found": True}
        assert context.user_input == "테스트 질문"


class TestAnswerContext:
    """AnswerContext DTO 테스트."""

    def test_to_prompt_context_with_user_input_only(self):
        """사용자 입력만 있는 경우."""
        context = AnswerContext(user_input="질문입니다")

        prompt = context.to_prompt_context()

        assert "질문입니다" in prompt

    def test_to_prompt_context_with_classification(self):
        """분류 정보 포함."""
        context = AnswerContext(
            classification={"major_category": "재활용"},
            user_input="질문",
        )

        prompt = context.to_prompt_context()

        assert "재활용" in prompt

    def test_to_prompt_context_with_disposal_rules(self):
        """분리배출 규칙 포함."""
        context = AnswerContext(
            disposal_rules={"method": "세척 후 배출"},
            user_input="질문",
        )

        prompt = context.to_prompt_context()

        assert "세척" in prompt

    def test_has_context_true(self):
        """컨텍스트 존재 확인."""
        context = AnswerContext(
            classification={"key": "value"},
            user_input="질문",
        )

        assert context.has_context()

    def test_has_context_false(self):
        """컨텍스트 없음 확인."""
        context = AnswerContext(user_input="질문")

        assert not context.has_context()
