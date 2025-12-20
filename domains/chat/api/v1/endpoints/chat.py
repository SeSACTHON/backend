"""Chat 엔드포인트

채팅 메시지 처리 API
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from domains.chat.api.v1.dependencies import ChatServiceDep
from domains.chat.schemas.chat import ChatMessageRequest, ChatMessageResponse
from domains.chat.security import UserInfo, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# 타입 별칭
# =============================================================================

CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


# =============================================================================
# 엔드포인트
# =============================================================================


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="메시지 전송 및 응답 수신",
    description="""
    폐기물 분리배출 관련 질문을 보내고 AI 어시스턴트의 답변을 받습니다.

    - **이미지 포함**: 이미지 URL을 함께 보내면 Vision AI가 이미지를 분석합니다.
    - **텍스트 전용**: 이미지 없이 텍스트만 보내도 답변을 받을 수 있습니다.
    """,
    responses={
        201: {
            "description": "성공적으로 응답 생성",
            "content": {
                "application/json": {
                    "example": {
                        "user_answer": "페트병은 내용물을 비우고 라벨을 제거한 후 투명 페트병 수거함에 버려주세요."
                    }
                }
            },
        },
        401: {"description": "인증 실패"},
        422: {"description": "요청 데이터 유효성 검사 실패"},
    },
)
async def send_message(
    payload: ChatMessageRequest,
    service: ChatServiceDep,
    user: CurrentUser,
) -> ChatMessageResponse:
    """채팅 메시지 전송

    Args:
        payload: 채팅 요청 (메시지, 이미지 URL)
        service: ChatService 인스턴스
        user: 현재 인증된 사용자

    Returns:
        ChatMessageResponse: AI 어시스턴트 응답
    """
    return await service.send_message(payload)
