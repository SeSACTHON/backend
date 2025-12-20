"""ChatService 단위 테스트

테스트 범위:
- send_message: 메인 진입점
- _run_pipeline: 파이프라인 분기 로직
- _run_image_pipeline: 이미지 파이프라인 실행
- _run_text_pipeline: 텍스트 파이프라인 실행
- _render_answer: 답변 렌더링
- _fallback_answer: 폴백 답변
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from domains._shared.schemas.waste import WasteClassificationResult
from domains.chat.schemas.chat import ChatMessageRequest, ChatMessageResponse
from domains.chat.services.chat import ChatService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def chat_service() -> ChatService:
    """ChatService 인스턴스 생성"""
    return ChatService()


@pytest.fixture
def mock_classification_result() -> dict:
    """Vision/Text 파이프라인 결과 mock"""
    return {
        "classification_result": {
            "classification": {
                "major_category": "재활용폐기물",
                "middle_category": "무색페트병",
                "minor_category": "음료수병",
            },
            "situation_tags": ["내용물_없음", "라벨_제거됨"],
        },
        "disposal_rules": {
            "배출방법_공통": "내용물을 비우고 라벨을 제거",
            "배출방법_세부": "투명 페트병 전용 수거함에 배출",
        },
        "final_answer": {
            "user_answer": "페트병은 내용물을 비우고 라벨을 제거한 후 투명 페트병 수거함에 버려주세요.",
            "disposal_steps": {
                "단계1": "내용물 비우기",
                "단계2": "라벨 제거",
                "단계3": "투명 페트병 수거함에 배출",
            },
            "insufficiencies": [],
        },
    }


@pytest.fixture
def waste_classification_result(
    mock_classification_result: dict,
) -> WasteClassificationResult:
    """WasteClassificationResult 인스턴스"""
    return WasteClassificationResult(**mock_classification_result)


# =============================================================================
# _fallback_answer 테스트
# =============================================================================


class TestFallbackAnswer:
    """_fallback_answer 메서드 테스트"""

    def test_returns_fixed_message(self, chat_service: ChatService) -> None:
        """고정된 폴백 메시지를 반환해야 함"""
        result = chat_service._fallback_answer("테스트 메시지")

        assert "이미지가 인식되지 않았어요" in result
        assert "다시 시도해주세요" in result

    def test_ignores_input_message(self, chat_service: ChatService) -> None:
        """입력 메시지와 무관하게 동일한 결과 반환"""
        result1 = chat_service._fallback_answer("메시지1")
        result2 = chat_service._fallback_answer("메시지2")

        assert result1 == result2


# =============================================================================
# _render_answer 테스트
# =============================================================================


class TestRenderAnswer:
    """_render_answer 메서드 테스트"""

    def test_extracts_user_answer(
        self,
        chat_service: ChatService,
        waste_classification_result: WasteClassificationResult,
    ) -> None:
        """final_answer에서 user_answer를 추출해야 함"""
        result = chat_service._render_answer(waste_classification_result, "원본 질문")

        assert (
            result == "페트병은 내용물을 비우고 라벨을 제거한 후 투명 페트병 수거함에 버려주세요."
        )

    def test_fallback_when_user_answer_missing(self, chat_service: ChatService) -> None:
        """user_answer가 없으면 폴백 반환"""
        result = WasteClassificationResult(
            classification_result={},
            disposal_rules={},
            final_answer={},
        )

        text = chat_service._render_answer(result, "원본 질문")

        assert text == chat_service._fallback_answer("원본 질문")

    def test_fallback_when_user_answer_empty(self, chat_service: ChatService) -> None:
        """user_answer가 빈 문자열이면 폴백 반환"""
        result = WasteClassificationResult(
            classification_result={},
            disposal_rules={},
            final_answer={"user_answer": "   "},
        )

        text = chat_service._render_answer(result, "원본 질문")

        assert text == chat_service._fallback_answer("원본 질문")

    def test_fallback_when_final_answer_empty_dict(self, chat_service: ChatService) -> None:
        """final_answer가 빈 dict이면 폴백 반환"""
        result = WasteClassificationResult(
            classification_result={},
            disposal_rules={},
            final_answer={},  # None 대신 빈 dict (스키마가 Dict[str, Any] 타입)
        )

        text = chat_service._render_answer(result, "원본 질문")

        assert text == chat_service._fallback_answer("원본 질문")


# =============================================================================
# _run_pipeline 테스트
# =============================================================================


class TestRunPipeline:
    """_run_pipeline 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_routes_to_image_pipeline_when_image_url_present(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """이미지 URL이 있으면 이미지 파이프라인으로 라우팅"""
        with patch.object(
            chat_service,
            "_run_image_pipeline",
            new_callable=AsyncMock,
            return_value=WasteClassificationResult(**mock_classification_result),
        ) as mock_image:
            with patch.object(
                chat_service,
                "_run_text_pipeline",
                new_callable=AsyncMock,
            ) as mock_text:
                result = await chat_service._run_pipeline("질문", "https://example.com/image.jpg")

                mock_image.assert_called_once_with("질문", "https://example.com/image.jpg")
                mock_text.assert_not_called()
                assert isinstance(result, WasteClassificationResult)

    @pytest.mark.asyncio
    async def test_routes_to_text_pipeline_when_no_image_url(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """이미지 URL이 없으면 텍스트 파이프라인으로 라우팅"""
        with patch.object(
            chat_service,
            "_run_image_pipeline",
            new_callable=AsyncMock,
        ) as mock_image:
            with patch.object(
                chat_service,
                "_run_text_pipeline",
                new_callable=AsyncMock,
                return_value=WasteClassificationResult(**mock_classification_result),
            ) as mock_text:
                result = await chat_service._run_pipeline("질문", None)

                mock_text.assert_called_once_with("질문")
                mock_image.assert_not_called()
                assert isinstance(result, WasteClassificationResult)


# =============================================================================
# _run_image_pipeline 테스트
# =============================================================================


class TestRunImagePipeline:
    """_run_image_pipeline 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_calls_process_waste_classification(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """process_waste_classification을 올바른 인자로 호출"""

        # asyncio.to_thread 자체를 Mock하여 동기 함수 호출을 우회
        async def mock_to_thread(func, *args, **kwargs):
            return mock_classification_result

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await chat_service._run_image_pipeline("질문", "https://example.com/image.jpg")

            assert isinstance(result, WasteClassificationResult)

    @pytest.mark.asyncio
    async def test_returns_waste_classification_result(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """WasteClassificationResult 인스턴스를 반환"""

        async def mock_to_thread(func, *args, **kwargs):
            return mock_classification_result

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await chat_service._run_image_pipeline("질문", "https://example.com/image.jpg")

            assert (
                result.classification_result == mock_classification_result["classification_result"]
            )
            assert result.disposal_rules == mock_classification_result["disposal_rules"]
            assert result.final_answer == mock_classification_result["final_answer"]


# =============================================================================
# _run_text_pipeline 테스트
# =============================================================================


class TestRunTextPipeline:
    """_run_text_pipeline 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_calls_text_pipeline_components(
        self,
        chat_service: ChatService,
    ) -> None:
        """텍스트 파이프라인 구성요소들을 순서대로 호출"""
        mock_result = {
            "classification_result": {"major_category": "재활용폐기물"},
            "disposal_rules": {"배출방법_공통": "비우고 버리기"},
            "final_answer": {"user_answer": "답변입니다"},
        }

        # asyncio.to_thread를 Mock하여 _execute_text_pipeline 우회
        async def mock_to_thread(func, *args, **kwargs):
            return mock_result

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await chat_service._run_text_pipeline("페트병 버리는 법")

            assert isinstance(result, WasteClassificationResult)
            assert result.final_answer == mock_result["final_answer"]

    @pytest.mark.asyncio
    async def test_handles_pipeline_error(
        self,
        chat_service: ChatService,
    ) -> None:
        """파이프라인 에러 발생 시 PipelineExecutionError 래핑"""
        from domains.chat.services.chat import PipelineExecutionError

        async def mock_to_thread_error(func, *args, **kwargs):
            raise RuntimeError("테스트 에러")

        with patch("asyncio.to_thread", side_effect=mock_to_thread_error):
            with pytest.raises(PipelineExecutionError) as exc_info:
                await chat_service._run_text_pipeline("질문")

            assert "text pipeline failed" in str(exc_info.value)


# =============================================================================
# _execute_text_pipeline 테스트
# =============================================================================


class TestExecuteTextPipeline:
    """_execute_text_pipeline 인스턴스 메서드 테스트"""

    def test_returns_dict_with_required_keys(self, chat_service: ChatService) -> None:
        """필수 키를 포함한 dict 반환"""
        mock_classification = {"classification": {"major_category": "재활용폐기물"}}
        mock_rules = {"배출방법_공통": "비우고 버리기"}
        mock_answer = {"user_answer": "답변입니다"}

        # 인스턴스의 _text_classifier를 직접 Mock
        chat_service._text_classifier = lambda user_input, save_result: mock_classification

        with patch(
            "domains.chat.services.chat.get_disposal_rules",
            return_value=mock_rules,
        ):
            with patch(
                "domains.chat.services.chat.generate_answer",
                return_value=mock_answer,
            ):
                result = chat_service._execute_text_pipeline("질문")

                assert "classification_result" in result
                assert "disposal_rules" in result
                assert "final_answer" in result


# =============================================================================
# send_message 테스트
# =============================================================================


class TestSendMessage:
    """send_message 메서드 테스트 (통합)"""

    @pytest.mark.asyncio
    async def test_success_with_image(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """이미지가 있는 요청 성공 케이스"""
        request = ChatMessageRequest(
            message="이거 어떻게 버려요?",
            image_url="https://example.com/pet-bottle.jpg",
        )

        with patch.object(
            chat_service,
            "_run_pipeline",
            new_callable=AsyncMock,
            return_value=WasteClassificationResult(**mock_classification_result),
        ):
            response = await chat_service.send_message(request)

            assert isinstance(response, ChatMessageResponse)
            assert "페트병" in response.user_answer

    @pytest.mark.asyncio
    async def test_success_without_image(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """이미지가 없는 텍스트 전용 요청 성공 케이스"""
        request = ChatMessageRequest(message="페트병 분리수거 방법 알려줘")

        with patch.object(
            chat_service,
            "_run_pipeline",
            new_callable=AsyncMock,
            return_value=WasteClassificationResult(**mock_classification_result),
        ):
            response = await chat_service.send_message(request)

            assert isinstance(response, ChatMessageResponse)
            assert len(response.user_answer) > 0

    @pytest.mark.asyncio
    async def test_fallback_on_pipeline_error(
        self,
        chat_service: ChatService,
    ) -> None:
        """파이프라인 에러 시 폴백 응답 반환"""
        request = ChatMessageRequest(message="질문입니다")

        with patch.object(
            chat_service,
            "_run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Pipeline failed"),
        ):
            response = await chat_service.send_message(request)

            assert isinstance(response, ChatMessageResponse)
            assert response.user_answer == chat_service._fallback_answer("질문입니다")

    @pytest.mark.asyncio
    async def test_logs_message_info(
        self,
        chat_service: ChatService,
        mock_classification_result: dict,
    ) -> None:
        """메시지 정보를 로깅"""
        request = ChatMessageRequest(
            message="테스트 메시지",
            image_url="https://example.com/image.jpg",
        )

        with patch.object(
            chat_service,
            "_run_pipeline",
            new_callable=AsyncMock,
            return_value=WasteClassificationResult(**mock_classification_result),
        ):
            with patch("domains.chat.services.chat.logger") as mock_logger:
                await chat_service.send_message(request)

                mock_logger.info.assert_called()


# =============================================================================
# ChatMessageRequest 스키마 테스트
# =============================================================================


class TestChatMessageRequest:
    """ChatMessageRequest Pydantic 모델 테스트"""

    def test_valid_request_with_image(self) -> None:
        """이미지 URL 포함 유효한 요청"""
        request = ChatMessageRequest(
            message="질문입니다",
            image_url="https://example.com/image.jpg",
        )

        assert request.message == "질문입니다"
        assert str(request.image_url) == "https://example.com/image.jpg"
        assert request.temperature == 0.2  # 기본값

    def test_valid_request_without_image(self) -> None:
        """이미지 없는 유효한 요청"""
        request = ChatMessageRequest(message="질문입니다")

        assert request.message == "질문입니다"
        assert request.image_url is None

    def test_custom_temperature(self) -> None:
        """커스텀 temperature 설정"""
        request = ChatMessageRequest(message="질문", temperature=0.8)

        assert request.temperature == 0.8

    def test_invalid_image_url(self) -> None:
        """잘못된 이미지 URL은 ValidationError"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatMessageRequest(
                message="질문",
                image_url="not-a-valid-url",
            )


# =============================================================================
# ChatMessageResponse 스키마 테스트
# =============================================================================


class TestChatMessageResponse:
    """ChatMessageResponse Pydantic 모델 테스트"""

    def test_valid_response(self) -> None:
        """유효한 응답 생성"""
        response = ChatMessageResponse(user_answer="답변입니다")

        assert response.user_answer == "답변입니다"

    def test_empty_answer_allowed(self) -> None:
        """빈 답변도 허용"""
        response = ChatMessageResponse(user_answer="")

        assert response.user_answer == ""
