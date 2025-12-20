"""Tracing 모듈 테스트

OpenTelemetry 설정 및 환경변수 기반 분기 테스트
"""

from unittest.mock import MagicMock, patch


class TestTracingDisabled:
    """OTEL_ENABLED=false 일 때 동작 테스트"""

    @patch.dict("os.environ", {"OTEL_ENABLED": "false"})
    def test_configure_tracing_returns_false_when_disabled(self) -> None:
        """트레이싱 비활성화 시 False 반환"""
        # 모듈 재로드 필요 (환경변수 변경 반영)
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        result = tracing_module.configure_tracing(
            service_name="test",
            service_version="1.0.0",
        )
        assert result is False

    @patch.dict("os.environ", {"OTEL_ENABLED": "false"})
    def test_instrument_fastapi_does_nothing_when_disabled(self) -> None:
        """비활성화 시 FastAPI 계측 안함"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        mock_app = MagicMock()
        # 예외 없이 반환
        tracing_module.instrument_fastapi(mock_app)

    @patch.dict("os.environ", {"OTEL_ENABLED": "false"})
    def test_instrument_httpx_does_nothing_when_disabled(self) -> None:
        """비활성화 시 HTTPX 계측 안함"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        # 예외 없이 반환
        tracing_module.instrument_httpx()

    @patch.dict("os.environ", {"OTEL_ENABLED": "false"})
    def test_get_tracer_returns_none_when_disabled(self) -> None:
        """비활성화 시 get_tracer는 None 반환"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        result = tracing_module.get_tracer("test")
        assert result is None


class TestTracingEnabled:
    """OTEL_ENABLED=true 일 때 동작 테스트"""

    @patch.dict("os.environ", {"OTEL_ENABLED": "true"})
    def test_shutdown_tracing_without_provider(self) -> None:
        """TracerProvider 없이 shutdown 호출해도 에러 없음"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        # _tracer_provider가 None일 때
        tracing_module._tracer_provider = None
        tracing_module.shutdown_tracing()  # 예외 없이 반환

    @patch.dict("os.environ", {"OTEL_ENABLED": "true"})
    def test_create_span_returns_nullcontext_when_tracer_none(self) -> None:
        """tracer가 None일 때 nullcontext 반환"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        # get_tracer가 None을 반환하도록 mock
        with patch.object(tracing_module, "get_tracer", return_value=None):
            span = tracing_module.create_span("test_span")
            # nullcontext여야 함
            from contextlib import nullcontext

            assert isinstance(span, type(nullcontext()))


class TestTracingEnvironmentVariables:
    """환경변수 파싱 테스트"""

    @patch.dict(
        "os.environ",
        {
            "OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "custom-endpoint:4317",
            "OTEL_SAMPLING_RATE": "0.5",
        },
    )
    def test_custom_endpoint_from_env(self) -> None:
        """커스텀 엔드포인트 환경변수 적용"""
        import importlib

        import domains.chat.core.tracing as tracing_module

        importlib.reload(tracing_module)

        assert tracing_module.OTEL_EXPORTER_ENDPOINT == "custom-endpoint:4317"
        assert tracing_module.OTEL_SAMPLING_RATE == 0.5
