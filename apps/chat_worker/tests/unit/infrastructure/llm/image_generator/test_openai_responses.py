"""OpenAI Responses API Image Generator Tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import os

import pytest

from chat_worker.application.ports.image_generator import (
    ImageGenerationError,
    ReferenceImage,
)
from chat_worker.infrastructure.llm.image_generator.openai_responses import (
    DEFAULT_IMAGE_TIMEOUT,
    OpenAIResponsesImageGenerator,
)


class TestOpenAIResponsesImageGeneratorInit:
    """초기화 테스트."""

    def test_default_values(self):
        """기본값 초기화."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()
            assert gen._model == "gpt-5.2"
            assert gen._default_size == "1024x1024"
            assert gen._default_quality == "medium"

    def test_custom_values(self):
        """커스텀 값 초기화."""
        gen = OpenAIResponsesImageGenerator(
            model="gpt-5.1",
            api_key="custom-key",
            default_size="1792x1024",
            default_quality="high",
        )
        assert gen._model == "gpt-5.1"
        assert gen._default_size == "1792x1024"
        assert gen._default_quality == "high"


class TestOpenAIResponsesImageGeneratorProperties:
    """프로퍼티 테스트."""

    def test_supports_reference_images(self):
        """참조 이미지 지원 여부."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()
            assert gen.supports_reference_images is True

    def test_max_reference_images(self):
        """최대 참조 이미지 개수."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()
            assert gen.max_reference_images == 1


class TestOpenAIResponsesImageGeneratorGenerate:
    """generate() 테스트."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """이미지 생성 성공."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()

            # Mock response
            mock_image_item = MagicMock()
            mock_image_item.type = "image_generation_call"
            mock_image_item.result = "https://example.com/image.png"

            mock_message_item = MagicMock()
            mock_message_item.type = "message"
            mock_message_item.content = [MagicMock(text="생성된 이미지 설명")]

            mock_response = MagicMock()
            mock_response.output = [mock_image_item, mock_message_item]

            with patch.object(
                gen._client.responses,
                "create",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                result = await gen.generate(
                    prompt="테스트 이미지",
                    size="1024x1024",
                    quality="medium",
                )

                assert result.image_url == "https://example.com/image.png"
                assert result.description == "생성된 이미지 설명"
                assert result.provider == "openai"
                assert result.model == "gpt-5.2"

    @pytest.mark.asyncio
    async def test_generate_no_image_raises(self):
        """이미지 없음 시 에러."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()

            mock_response = MagicMock()
            mock_response.output = []

            with patch.object(
                gen._client.responses,
                "create",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                with pytest.raises(ImageGenerationError) as exc_info:
                    await gen.generate("테스트")
                assert "No image generated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """API 에러 시 ImageGenerationError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()

            with patch.object(
                gen._client.responses,
                "create",
                new_callable=AsyncMock,
                side_effect=Exception("API Error"),
            ):
                with pytest.raises(ImageGenerationError) as exc_info:
                    await gen.generate("테스트")
                assert "API Error" in str(exc_info.value)
                assert exc_info.value.cause is not None


class TestOpenAIResponsesImageGeneratorGenerateWithReference:
    """generate_with_reference() 테스트."""

    @pytest.mark.asyncio
    async def test_with_reference(self):
        """참조 이미지로 생성."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()

            mock_image_item = MagicMock()
            mock_image_item.type = "image_generation_call"
            mock_image_item.result = "https://example.com/ref_image.png"

            mock_response = MagicMock()
            mock_response.output = [mock_image_item]

            with patch.object(
                gen._client.responses,
                "create",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_create:
                ref = ReferenceImage(image_bytes=b"test_image")
                result = await gen.generate_with_reference(
                    prompt="캐릭터 생성",
                    reference_images=[ref],
                )

                assert result.image_url == "https://example.com/ref_image.png"
                # 멀티모달 입력 확인
                call_args = mock_create.call_args
                assert call_args is not None

    @pytest.mark.asyncio
    async def test_without_reference_fallback(self):
        """참조 이미지 없으면 기본 생성."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()

            mock_image_item = MagicMock()
            mock_image_item.type = "image_generation_call"
            mock_image_item.result = "https://example.com/image.png"

            mock_response = MagicMock()
            mock_response.output = [mock_image_item]

            with patch.object(
                gen._client.responses,
                "create",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                result = await gen.generate_with_reference(
                    prompt="테스트",
                    reference_images=[],
                )
                assert result.image_url is not None


class TestBuildInputPrompt:
    """_build_input_prompt() 테스트."""

    def test_prompt_format(self):
        """프롬프트 형식."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()
            prompt = gen._build_input_prompt("테스트 요청")

            assert "테스트 요청" in prompt
            assert "이미지를 생성해주세요" in prompt
            assert "한국어로 작성해주세요" in prompt


class TestBuildMultimodalInput:
    """_build_multimodal_input() 테스트."""

    def test_multimodal_format(self):
        """멀티모달 입력 형식."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            gen = OpenAIResponsesImageGenerator()
            ref = ReferenceImage(
                image_bytes=b"test_image_data",
                mime_type="image/png",
            )
            inputs = gen._build_multimodal_input("테스트 요청", ref)

            assert len(inputs) == 2
            assert inputs[0]["type"] == "input_text"
            assert "테스트 요청" in inputs[0]["text"]
            assert inputs[1]["type"] == "input_image"
            assert inputs[1]["image_url"].startswith("data:image/png;base64,")


class TestDefaultImageTimeout:
    """타임아웃 설정 테스트."""

    def test_timeout_values(self):
        """타임아웃 값 확인."""
        assert DEFAULT_IMAGE_TIMEOUT.connect == 5.0
        assert DEFAULT_IMAGE_TIMEOUT.read == 60.0
        assert DEFAULT_IMAGE_TIMEOUT.write == 5.0
        assert DEFAULT_IMAGE_TIMEOUT.pool == 5.0
