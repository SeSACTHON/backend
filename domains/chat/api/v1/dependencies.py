"""FastAPI 의존성 정의

서비스 및 리소스 인스턴스 관리
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from domains.chat.services.chat import ChatService


# =============================================================================
# 서비스 팩토리
# =============================================================================


@lru_cache
def get_chat_service() -> ChatService:
    """ChatService 싱글톤 인스턴스 반환

    Returns:
        ChatService: 채팅 서비스 인스턴스
    """
    return ChatService()


# =============================================================================
# 의존성 타입 별칭 (FastAPI Annotated 패턴)
# =============================================================================

ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
