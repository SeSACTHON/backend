"""Unit tests for RedisOutboxRepository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestRedisOutboxRepository:
    """Tests for RedisOutboxRepository class."""

    @patch("redis.from_url")
    def test_init(self, mock_from_url):
        """Should initialize with Redis URL."""
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")

        mock_from_url.assert_called_once_with("redis://localhost:6379/0")
        assert repo._redis is mock_redis

    @patch("redis.from_url")
    def test_push_success(self, mock_from_url):
        """Should LPUSH data and return True on success."""
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.push("test:key", '{"event": "data"}')

        assert result is True
        mock_redis.lpush.assert_called_once_with("test:key", '{"event": "data"}')

    @patch("redis.from_url")
    def test_push_failure(self, mock_from_url):
        """Should return False when LPUSH fails."""
        mock_redis = MagicMock()
        mock_redis.lpush.side_effect = Exception("Redis error")
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.push("test:key", '{"event": "data"}')

        assert result is False

    @patch("redis.from_url")
    def test_pop_success_bytes(self, mock_from_url):
        """Should RPOP and decode bytes to string."""
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = b'{"event": "data"}'
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.pop("test:key")

        assert result == '{"event": "data"}'
        mock_redis.rpop.assert_called_once_with("test:key")

    @patch("redis.from_url")
    def test_pop_success_string(self, mock_from_url):
        """Should handle string result from RPOP."""
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = '{"event": "data"}'
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.pop("test:key")

        assert result == '{"event": "data"}'

    @patch("redis.from_url")
    def test_pop_empty(self, mock_from_url):
        """Should return None when queue is empty."""
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = None
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.pop("test:key")

        assert result is None

    @patch("redis.from_url")
    def test_pop_failure(self, mock_from_url):
        """Should return None when RPOP fails."""
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = Exception("Redis error")
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.pop("test:key")

        assert result is None

    @patch("redis.from_url")
    def test_length_success(self, mock_from_url):
        """Should return queue length."""
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 5
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.length("test:key")

        assert result == 5
        mock_redis.llen.assert_called_once_with("test:key")

    @patch("redis.from_url")
    def test_length_failure(self, mock_from_url):
        """Should return 0 when LLEN fails."""
        mock_redis = MagicMock()
        mock_redis.llen.side_effect = Exception("Redis error")
        mock_from_url.return_value = mock_redis

        from domains.auth.infrastructure.messaging.redis_outbox import RedisOutboxRepository

        repo = RedisOutboxRepository("redis://localhost:6379/0")
        result = repo.length("test:key")

        assert result == 0

