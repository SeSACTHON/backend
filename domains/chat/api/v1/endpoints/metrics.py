from fastapi import APIRouter, Depends

from domains.chat.api.v1.dependencies import get_chat_service
from domains.chat.services.chat import ChatService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", summary="Chat service metrics")
async def metrics(service: ChatService = Depends(get_chat_service)):
    return await service.metrics()
