"""Constants 모듈 테스트

버킷 생성 함수 및 상수 검증
"""

import pytest

from domains.chat.core.constants import (
    # 상수
    BUCKETS_EXTENDED,
    BUCKETS_FAST,
    BUCKETS_MEDIUM,
    BUCKETS_PIPELINE,
    FALLBACK_MESSAGE,
    MESSAGE_MAX_LENGTH,
    MESSAGE_MIN_LENGTH,
    PIPELINE_DURATION_BUCKETS,
    PIPELINE_TYPE_IMAGE,
    PIPELINE_TYPE_TEXT,
    SERVICE_NAME,
    SERVICE_VERSION,
    # 함수
    exponential_buckets,
    exponential_buckets_range,
    linear_buckets,
    merge_buckets,
)


class TestLinearBuckets:
    """linear_buckets 함수 테스트"""

    def test_generates_correct_sequence(self) -> None:
        """선형 시퀀스 생성 검증"""
        result = linear_buckets(1.0, 0.5, 5)
        assert result == (1.0, 1.5, 2.0, 2.5, 3.0)

    def test_single_bucket(self) -> None:
        """단일 버킷 생성"""
        result = linear_buckets(0.1, 0.1, 1)
        assert result == (0.1,)

    def test_zero_width(self) -> None:
        """간격 0인 경우"""
        result = linear_buckets(1.0, 0.0, 3)
        assert result == (1.0, 1.0, 1.0)

    def test_negative_width(self) -> None:
        """음수 간격 (감소 시퀀스)"""
        result = linear_buckets(1.0, -0.2, 3)
        assert result == (1.0, 0.8, 0.6)

    def test_raises_on_invalid_count(self) -> None:
        """count < 1이면 ValueError"""
        with pytest.raises(ValueError, match="count must be positive"):
            linear_buckets(1.0, 0.5, 0)

        with pytest.raises(ValueError, match="count must be positive"):
            linear_buckets(1.0, 0.5, -1)


class TestExponentialBuckets:
    """exponential_buckets 함수 테스트"""

    def test_generates_correct_sequence(self) -> None:
        """지수 시퀀스 생성 검증"""
        result = exponential_buckets(0.1, 2, 5)
        assert result == (0.1, 0.2, 0.4, 0.8, 1.6)

    def test_single_bucket(self) -> None:
        """단일 버킷 생성"""
        result = exponential_buckets(1.0, 2, 1)
        assert result == (1.0,)

    def test_large_factor(self) -> None:
        """큰 배율 테스트"""
        result = exponential_buckets(1.0, 10, 3)
        assert result == (1.0, 10.0, 100.0)

    def test_raises_on_invalid_count(self) -> None:
        """count < 1이면 ValueError"""
        with pytest.raises(ValueError, match="count must be positive"):
            exponential_buckets(0.1, 2, 0)

    def test_raises_on_invalid_start(self) -> None:
        """start <= 0이면 ValueError"""
        with pytest.raises(ValueError, match="start must be positive"):
            exponential_buckets(0, 2, 5)

        with pytest.raises(ValueError, match="start must be positive"):
            exponential_buckets(-1, 2, 5)

    def test_raises_on_invalid_factor(self) -> None:
        """factor <= 1이면 ValueError"""
        with pytest.raises(ValueError, match="factor must be greater than 1"):
            exponential_buckets(0.1, 1, 5)

        with pytest.raises(ValueError, match="factor must be greater than 1"):
            exponential_buckets(0.1, 0.5, 5)


class TestExponentialBucketsRange:
    """exponential_buckets_range 함수 테스트"""

    def test_generates_range(self) -> None:
        """범위 기반 지수 버킷 생성"""
        result = exponential_buckets_range(1.0, 100.0, 3)
        # 1.0, 10.0, 100.0 예상 (factor = 10)
        assert len(result) == 3
        assert result[0] == 1.0
        assert result[-1] == 100.0

    def test_two_buckets_in_range(self) -> None:
        """count=2인 경우 시작값과 끝값 반환"""
        result = exponential_buckets_range(1.0, 100.0, 2)
        assert len(result) == 2
        assert result[0] == 1.0
        assert result[-1] == 100.0

    def test_raises_on_invalid_count(self) -> None:
        """count < 1이면 ValueError"""
        with pytest.raises(ValueError, match="count must be positive"):
            exponential_buckets_range(1.0, 10.0, 0)

    def test_raises_on_invalid_min(self) -> None:
        """min <= 0이면 ValueError"""
        with pytest.raises(ValueError, match="min must be positive"):
            exponential_buckets_range(0, 10.0, 5)

    def test_raises_on_invalid_max(self) -> None:
        """max <= min이면 ValueError"""
        with pytest.raises(ValueError, match="max must be greater than min"):
            exponential_buckets_range(10.0, 10.0, 5)

        with pytest.raises(ValueError, match="max must be greater than min"):
            exponential_buckets_range(10.0, 5.0, 5)


class TestMergeBuckets:
    """merge_buckets 함수 테스트"""

    def test_merges_and_sorts(self) -> None:
        """병합 및 정렬 검증"""
        result = merge_buckets((0.5, 0.1), (0.3, 0.2))
        assert result == (0.1, 0.2, 0.3, 0.5)

    def test_removes_duplicates(self) -> None:
        """중복 제거 검증"""
        result = merge_buckets((0.1, 0.5, 1.0), (0.5, 2.0, 5.0))
        assert result == (0.1, 0.5, 1.0, 2.0, 5.0)

    def test_empty_input(self) -> None:
        """빈 입력"""
        result = merge_buckets()
        assert result == ()

    def test_single_set(self) -> None:
        """단일 세트"""
        result = merge_buckets((3.0, 1.0, 2.0))
        assert result == (1.0, 2.0, 3.0)


class TestBucketConstants:
    """버킷 상수 검증"""

    def test_buckets_fast_is_sorted(self) -> None:
        """BUCKETS_FAST가 정렬되어 있음"""
        assert BUCKETS_FAST == tuple(sorted(BUCKETS_FAST))

    def test_buckets_medium_is_sorted(self) -> None:
        """BUCKETS_MEDIUM이 정렬되어 있음"""
        assert BUCKETS_MEDIUM == tuple(sorted(BUCKETS_MEDIUM))

    def test_buckets_pipeline_is_sorted(self) -> None:
        """BUCKETS_PIPELINE이 정렬되어 있음"""
        assert BUCKETS_PIPELINE == tuple(sorted(BUCKETS_PIPELINE))

    def test_buckets_extended_is_sorted(self) -> None:
        """BUCKETS_EXTENDED가 정렬되어 있음"""
        assert BUCKETS_EXTENDED == tuple(sorted(BUCKETS_EXTENDED))

    def test_buckets_extended_includes_pipeline(self) -> None:
        """BUCKETS_EXTENDED가 PIPELINE을 포함"""
        for bucket in BUCKETS_PIPELINE:
            assert bucket in BUCKETS_EXTENDED

    def test_pipeline_duration_buckets_alias(self) -> None:
        """PIPELINE_DURATION_BUCKETS는 BUCKETS_EXTENDED와 동일"""
        assert PIPELINE_DURATION_BUCKETS == BUCKETS_EXTENDED


class TestServiceConstants:
    """서비스 상수 검증"""

    def test_service_name(self) -> None:
        """서비스 이름 형식"""
        assert SERVICE_NAME == "chat-api"

    def test_service_version_format(self) -> None:
        """서비스 버전 형식 (semantic versioning)"""
        parts = SERVICE_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_pipeline_types(self) -> None:
        """파이프라인 타입 값"""
        assert PIPELINE_TYPE_IMAGE == "image"
        assert PIPELINE_TYPE_TEXT == "text"

    def test_fallback_message_not_empty(self) -> None:
        """폴백 메시지가 비어있지 않음"""
        assert len(FALLBACK_MESSAGE) > 0

    def test_message_length_constraints(self) -> None:
        """메시지 길이 제약 유효성"""
        assert MESSAGE_MIN_LENGTH >= 0
        assert MESSAGE_MAX_LENGTH > MESSAGE_MIN_LENGTH
