"""Logging 모듈 테스트

ECS JSON 포맷터 및 PII 마스킹 테스트
"""

import logging
from unittest.mock import patch

import pytest

from domains.chat.core.logging import (
    ECSJsonFormatter,
    configure_logging,
    mask_sensitive_data,
)


class TestMaskSensitiveData:
    """PII 마스킹 함수 테스트"""

    def test_masks_password_field(self) -> None:
        """password 필드 마스킹"""
        data = {"password": "secret123"}
        result = mask_sensitive_data(data)
        assert result["password"] == "***REDACTED***"

    def test_masks_token_field(self) -> None:
        """token 필드 마스킹"""
        data = {"token": "abc123xyz"}
        result = mask_sensitive_data(data)
        assert result["token"] == "***REDACTED***"

    def test_masks_api_key_field_partial(self) -> None:
        """api_key 필드 부분 마스킹 (긴 값은 앞뒤 4자만 노출)"""
        data = {"api_key": "sk-1234567890abcdef"}
        result = mask_sensitive_data(data)
        # 길이 > 10이면 부분 마스킹: "sk-1...cdef"
        assert result["api_key"].startswith("sk-1")
        assert result["api_key"].endswith("cdef")
        assert "..." in result["api_key"]

    def test_masks_authorization_field_partial(self) -> None:
        """authorization 필드 부분 마스킹"""
        data = {"authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."}
        result = mask_sensitive_data(data)
        # 부분 마스킹
        assert "..." in result["authorization"]

    def test_masks_short_value_completely(self) -> None:
        """짧은 값은 완전 마스킹"""
        data = {"password": "short"}  # 5자 <= 10 (MASK_MIN_LENGTH)
        result = mask_sensitive_data(data)
        assert result["password"] == "***REDACTED***"

    def test_case_insensitive_matching(self) -> None:
        """대소문자 무관하게 마스킹"""
        data = {"PASSWORD": "secret", "Token": "abc123", "API_KEY": "key"}
        result = mask_sensitive_data(data)
        assert result["PASSWORD"] == "***REDACTED***"
        assert result["Token"] == "***REDACTED***"
        assert result["API_KEY"] == "***REDACTED***"

    def test_nested_dict_masking(self) -> None:
        """중첩 dict 마스킹"""
        data = {
            "user": {
                "password": "secret",
                "name": "John",
            }
        }
        result = mask_sensitive_data(data)
        assert result["user"]["password"] == "***REDACTED***"
        assert result["user"]["name"] == "John"

    def test_list_with_dicts_masking(self) -> None:
        """리스트 내 dict 마스킹"""
        data = {
            "users": [
                {"password": "pass1"},
                {"password": "pass2"},
            ]
        }
        result = mask_sensitive_data(data)
        assert result["users"][0]["password"] == "***REDACTED***"
        assert result["users"][1]["password"] == "***REDACTED***"

    def test_non_sensitive_fields_unchanged(self) -> None:
        """민감하지 않은 필드는 변경 안됨"""
        data = {"username": "john", "email": "john@example.com", "age": 30}
        result = mask_sensitive_data(data)
        assert result == data

    def test_none_value_masked(self) -> None:
        """None 값도 민감 필드면 마스킹됨"""
        data = {"password": None}
        result = mask_sensitive_data(data)
        # None은 MASK_PLACEHOLDER로 대체
        assert result["password"] == "***REDACTED***"

    def test_empty_dict(self) -> None:
        """빈 dict"""
        result = mask_sensitive_data({})
        assert result == {}


class TestECSJsonFormatter:
    """ECS JSON 포맷터 테스트"""

    @pytest.fixture
    def formatter(self) -> ECSJsonFormatter:
        """포맷터 fixture"""
        return ECSJsonFormatter()

    @pytest.fixture
    def log_record(self) -> logging.LogRecord:
        """로그 레코드 fixture"""
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    def test_format_returns_json(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """JSON 문자열 반환"""
        import json

        result = formatter.format(log_record)
        # JSON 파싱 가능해야 함
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_format_contains_timestamp(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """@timestamp 필드 포함"""
        import json

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "@timestamp" in parsed

    def test_format_contains_message(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """message 필드 포함"""
        import json

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"

    def test_format_contains_log_level(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """log.level 필드 포함"""
        import json

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["log.level"] == "info"

    def test_format_contains_ecs_version(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """ecs.version 필드 포함"""
        import json

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "ecs.version" in parsed

    def test_format_contains_service_info(
        self, formatter: ECSJsonFormatter, log_record: logging.LogRecord
    ) -> None:
        """service.* 필드 포함"""
        import json

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "service.name" in parsed
        assert "service.version" in parsed


class TestConfigureLogging:
    """configure_logging 함수 테스트"""

    @patch.dict(
        "os.environ",
        {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "WARNING",
            "LOG_FORMAT": "json",
        },
    )
    def test_configures_with_env_vars(self) -> None:
        """환경변수로 로깅 설정"""
        # 재설정
        configure_logging()

        root_logger = logging.getLogger()
        assert root_logger.level <= logging.WARNING

    @patch.dict("os.environ", {"LOG_FORMAT": "text"})
    def test_text_format_option(self) -> None:
        """TEXT 포맷 설정"""
        configure_logging()
        # 예외 없이 완료
