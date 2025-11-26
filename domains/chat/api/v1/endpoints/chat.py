from fastapi import APIRouter, Depends, HTTPException, status

from domains._shared.security import TokenPayload
from domains.chat.api.v1.dependencies import get_chat_service
from domains.chat.schemas.chat import (
    ChatFeedback,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSession,
)
from domains.chat.services.chat import ChatService
from domains.chat.security import access_token_dependency

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message and get assistant response",
)
async def send_message(
    payload: ChatMessageRequest,
    service: ChatService = Depends(get_chat_service),
    token: TokenPayload = Depends(access_token_dependency),
):
    return await service.send_message(payload, user_id=str(token.user_id))


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSession,
    summary="Retrieve chat session transcript",
)
async def get_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
    token: TokenPayload = Depends(access_token_dependency),
):
    session = await service.get_session(session_id, user_id=str(token.user_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}", summary="Delete chat session")
async def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
    token: TokenPayload = Depends(access_token_dependency),
):
    await service.delete_session(session_id, user_id=str(token.user_id))
    return {"message": f"session {session_id} deleted"}


@router.get("/suggestions", summary="Suggested starter prompts")
async def suggestions(service: ChatService = Depends(get_chat_service)):
    return await service.suggestions()


@router.post("/feedback", summary="Submit conversation feedback")
async def feedback(payload: ChatFeedback, service: ChatService = Depends(get_chat_service)):
    await service.submit_feedback(payload)
    return {"message": "feedback stored"}
