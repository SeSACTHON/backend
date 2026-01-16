"""Gemini Native Image Generator Tests."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat_worker.application.ports.image_generator import (
    ImageGenerationError,
    ReferenceImage,
)
from chat_worker.infrastructure.llm.image_generator.gemini_native import (
    MODEL_REFERENCE_LIMITS,
    SIZE_TO_ASPECT_RATIO,
    GeminiNativeImageGenerator,
)


class TestGeminiNativeImageGeneratorInit:
    """초기화 테스트."""

    def test_default_values(self):
        """기본값 초기화."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()
            assert gen._model == "gemini-3-pro-image-preview"
            assert gen._max_reference == 14

    def test_custom_values(self):
        """커스텀 값 초기화."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator(
                model="gemini-2.5-flash-image",
                api_key="custom-key",
            )
            assert gen._model == "gemini-2.5-flash-image"
            assert gen._max_reference == 3
            assert gen._api_key == "custom-key"

    def test_missing_api_key_raises(self):
        """API 키 없으면 ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            # GOOGLE_API_KEY 환경변수 제거
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

            with pytest.raises(ValueError) as exc_info:
                GeminiNativeImageGenerator(api_key=None)
            assert "Google API key required" in str(exc_info.value)

    def test_unknown_model_uses_default_reference_limit(self):
        """미등록 모델은 기본 참조 제한 사용."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator(model="unknown-model")
            assert gen._max_reference == 3


class TestGeminiNativeImageGeneratorProperties:
    """프로퍼티 테스트."""

    def test_supports_reference_images(self):
        """참조 이미지 지원."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()
            assert gen.supports_reference_images is True

    def test_max_reference_images_pro(self):
        """Pro 모델 참조 제한."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator(model="gemini-3-pro-image-preview")
            assert gen.max_reference_images == 14

    def test_max_reference_images_flash(self):
        """Flash 모델 참조 제한."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator(model="gemini-2.5-flash-image")
            assert gen.max_reference_images == 3


class TestGeminiNativeImageGeneratorGenerate:
    """generate() 테스트."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """이미지 생성 성공."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()

            # Mock response
            mock_image_part = MagicMock()
            mock_image_part.inline_data = MagicMock()
            mock_image_part.inline_data.data = b"generated_image_bytes"
            mock_image_part.text = None

            mock_text_part = MagicMock()
            mock_text_part.inline_data = None
            mock_text_part.text = "이미지 설명"

            mock_content = MagicMock()
            mock_content.parts = [mock_image_part, mock_text_part]

            mock_candidate = MagicMock()
            mock_candidate.content = mock_content

            mock_response = MagicMock()
            mock_response.candidates = [mock_candidate]

            with patch.object(
                gen._client.aio.models,
                "generate_content",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                result = await gen.generate(
                    prompt="테스트 이미지",
                    size="1024x1024",
                )

                assert result.image_url.startswith("data:image/png;base64,")
                assert result.image_bytes == b"generated_image_bytes"
                assert result.description == "이미지 설명"
                assert result.provider == "google"
                assert result.model == "gemini-3-pro-image-preview"

    @pytest.mark.asyncio
    async def test_generate_no_image_raises(self):
        """이미지 없음 시 에러."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()

            mock_text_part = MagicMock()
            mock_text_part.inline_data = None
            mock_text_part.text = "텍스트만"

            mock_content = MagicMock()
            mock_content.parts = [mock_text_part]

            mock_candidate = MagicMock()
            mock_candidate.content = mock_content

            mock_response = MagicMock()
            mock_response.candidates = [mock_candidate]

            with patch.object(
                gen._client.aio.models,
                "generate_content",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                with pytest.raises(ImageGenerationError) as exc_info:
                    await gen.generate("테스트")
                assert "No image generated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """API 에러 시 ImageGenerationError."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()

            with patch.object(
                gen._client.aio.models,
                "generate_content",
                new_callable=AsyncMock,
                side_effect=Exception("API Error"),
            ):
                with pytest.raises(ImageGenerationError) as exc_info:
                    await gen.generate("테스트")
                assert "API Error" in str(exc_info.value)
                assert exc_info.value.cause is not None


class TestGeminiNativeImageGeneratorGenerateWithReference:
    """generate_with_reference() 테스트."""

    @pytest.mark.asyncio
    async def test_with_reference(self):
        """참조 이미지로 생성."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator()

            mock_image_part = MagicMock()
            mock_image_part.inline_data = MagicMock()
            mock_image_part.inline_data.data = b"ref_generated"
            mock_image_part.text = None

            mock_content = MagicMock()
            mock_content.parts = [mock_image_part]

            mock_candidate = MagicMock()
            mock_candidate.content = mock_content

            mock_response = MagicMock()
            mock_response.candidates = [mock_candidate]

            with patch.object(
                gen._client.aio.models,
                "generate_content",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                refs = [
                    ReferenceImage(image_bytes=b"ref1"),
                    ReferenceImage(image_bytes=b"ref2"),
                ]
                result = await gen.generate_with_reference(
                    prompt="캐릭터 생성",
                    reference_images=refs,
                )

                assert result.image_bytes == b"ref_generated"

    @pytest.mark.asyncio
    async def test_reference_truncation(self):
        """참조 이미지 개수 제한."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            gen = GeminiNativeImageGenerator(model="gemini-2.5-flash-image")
            assert gen._max_reference == 3

            mock_image_part = MagicMock()
            mock_image_part.inline_data = MagicMock()
            mock_image_part.inline_data.data = b"image"
            mock_image_part.text = None

            mock_content = MagicMock()
            mock_content.parts = [mock_image_part]

            mock_candidate = MagicMock()
            mock_candidate.content = mock_content

            mock_response = MagicMock()
            mock_response.candidates = [mock_candidate]

            with patch.object(
                gen._client.aio.models,
                "generate_content",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_generate:
                refs = [ReferenceImage(image_bytes=b"ref") for _ in range(5)]
                await gen.generate_with_reference("테스트", refs)

                # 내부적으로 3개만 사용됨 (truncated)
                mock_generate.assert_called_once()


class TestConstants:
    """상수 테스트."""

    def test_model_reference_limits(self):
        """모델별 참조 제한."""
        assert MODEL_REFERENCE_LIMITS["gemini-3-pro-image-preview"] == 14
        assert MODEL_REFERENCE_LIMITS["gemini-2.5-flash-image"] == 3

    def test_size_to_aspect_ratio(self):
        """크기 → 비율 매핑."""
        assert SIZE_TO_ASPECT_RATIO["1024x1024"] == "1:1"
        assert SIZE_TO_ASPECT_RATIO["1024x1792"] == "9:16"
        assert SIZE_TO_ASPECT_RATIO["1792x1024"] == "16:9"
        assert SIZE_TO_ASPECT_RATIO["512x512"] == "1:1"

    def test_unknown_size_defaults_to_1_1(self):
        """미등록 크기는 1:1 기본값."""
        assert SIZE_TO_ASPECT_RATIO.get("unknown", "1:1") == "1:1"
