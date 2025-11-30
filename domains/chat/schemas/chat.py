from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    temperature: float = 0.2
    image_url: Optional[HttpUrl] = None


class ChatMessageResponse(BaseModel):
    session_id: str
    user_answer: str
