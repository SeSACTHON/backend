"""RedisProgressNotifier 단위 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chat_worker.infrastructure.events.redis_progress_notifier import (
    RedisProgressNotifier,
)


class TestRedisProgressNotifier:
    """RedisProgressNotifier 테스트 스위트."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Mock Redis 클라이언트."""
        redis = AsyncMock()
        redis.xadd = AsyncMock(return_value=b"1234567890-0")
        return redis

    @pytest.fixture
    def notifier(self, mock_redis: AsyncMock) -> RedisProgressNotifier:
        """테스트용 Notifier."""
        return RedisProgressNotifier(
            redis=mock_redis,
            stream_prefix="test:events",
            maxlen=500,
        )

    # ==========================================================
    # notify_stage Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_notify_stage_basic(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """기본 단계 알림."""
        event_id = await notifier.notify_stage(
            task_id="job-123",
            stage="intent",
            status="started",
        )

        assert event_id is not None
        mock_redis.xadd.assert_called_once()

        # 호출 인자 확인
        call_args = mock_redis.xadd.call_args
        stream_name = call_args[0][0]
        event_data = call_args[0][1]

        assert stream_name == "test:events:job-123"
        assert event_data["event_type"] == "stage"
        assert event_data["stage"] == "intent"
        assert event_data["status"] == "started"

    @pytest.mark.asyncio
    async def test_notify_stage_with_progress(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """진행률 포함 알림."""
        await notifier.notify_stage(
            task_id="job-123",
            stage="rag",
            status="processing",
            progress=50,
            message="규정 검색 중...",
        )

        call_args = mock_redis.xadd.call_args
        event_data = call_args[0][1]

        assert event_data["progress"] == 50
        assert event_data["message"] == "규정 검색 중..."

    @pytest.mark.asyncio
    async def test_notify_stage_with_result(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """결과 포함 알림."""
        await notifier.notify_stage(
            task_id="job-123",
            stage="intent",
            status="completed",
            result={"intent": "waste", "confidence": 0.95},
        )

        call_args = mock_redis.xadd.call_args
        event_data = call_args[0][1]

        # result는 JSON 문자열로 저장됨
        assert "result" in event_data
        assert "waste" in event_data["result"]

    @pytest.mark.asyncio
    async def test_notify_stage_uses_maxlen(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """maxlen 파라미터 사용."""
        await notifier.notify_stage(
            task_id="job-123",
            stage="test",
            status="started",
        )

        call_args = mock_redis.xadd.call_args
        assert call_args.kwargs.get("maxlen") == 500

    # ==========================================================
    # notify_token Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_notify_token(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """토큰 스트리밍 알림."""
        await notifier.notify_token(
            task_id="job-456",
            content="안녕",
        )

        call_args = mock_redis.xadd.call_args
        event_data = call_args[0][1]

        assert event_data["event_type"] == "token"
        assert event_data["content"] == "안녕"

    @pytest.mark.asyncio
    async def test_notify_token_multiple(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """여러 토큰 연속 알림."""
        tokens = ["안녕", "하세요", "!"]

        for token in tokens:
            await notifier.notify_token(task_id="job-789", content=token)

        assert mock_redis.xadd.call_count == 3

    # ==========================================================
    # notify_needs_input Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_notify_needs_input(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """입력 요청 알림."""
        await notifier.notify_needs_input(
            task_id="job-abc",
            input_type="location",
            message="위치 정보를 입력해주세요.",
            timeout=60,
        )

        call_args = mock_redis.xadd.call_args
        event_data = call_args[0][1]

        assert event_data["event_type"] == "needs_input"
        assert event_data["input_type"] == "location"
        assert event_data["message"] == "위치 정보를 입력해주세요."
        # timeout은 문자열로 저장됨
        assert event_data["timeout"] == "60"

    @pytest.mark.asyncio
    async def test_notify_needs_input_default_timeout(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """기본 타임아웃."""
        await notifier.notify_needs_input(
            task_id="job-def",
            input_type="confirmation",
            message="계속할까요?",
        )

        call_args = mock_redis.xadd.call_args
        event_data = call_args[0][1]

        assert event_data["timeout"] == "60"  # 기본값 (문자열)

    # ==========================================================
    # Stream Name Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_stream_name_format(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """스트림 이름 형식."""
        await notifier.notify_stage(
            task_id="my-task-id",
            stage="test",
            status="started",
        )

        call_args = mock_redis.xadd.call_args
        stream_name = call_args[0][0]

        assert stream_name == "test:events:my-task-id"

    @pytest.mark.asyncio
    async def test_different_tasks_different_streams(
        self,
        notifier: RedisProgressNotifier,
        mock_redis: AsyncMock,
    ):
        """다른 task_id는 다른 스트림."""
        await notifier.notify_stage(task_id="task-1", stage="a", status="s")
        await notifier.notify_stage(task_id="task-2", stage="b", status="s")

        calls = mock_redis.xadd.call_args_list
        streams = [call[0][0] for call in calls]

        assert "test:events:task-1" in streams
        assert "test:events:task-2" in streams
