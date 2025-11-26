from functools import lru_cache

from domains.chat.core.config import get_settings
from domains.chat.core.redis import get_session_redis
from domains.chat.services.chat import ChatService
from domains.chat.services.session_store import ChatSessionStore


@lru_cache
def get_session_store() -> ChatSessionStore:
    settings = get_settings()
    redis = get_session_redis()
    return ChatSessionStore(
        redis,
        ttl_seconds=settings.session_ttl_seconds,
        max_history=settings.session_history_limit,
    )


def get_chat_service() -> ChatService:
    return ChatService(session_store=get_session_store())
