"""Chat API 스키마 정의

요청/응답 Pydantic 모델
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl

from domains.chat.core.constants import MESSAGE_MAX_LENGTH, MESSAGE_MIN_LENGTH


# =============================================================================
# 요청 스키마
# =============================================================================


class ChatMessageRequest(BaseModel):
    """채팅 메시지 요청"""

    message: str = Field(
        ...,
        min_length=MESSAGE_MIN_LENGTH,
        max_length=MESSAGE_MAX_LENGTH,
        description=f"사용자 메시지 ({MESSAGE_MIN_LENGTH}-{MESSAGE_MAX_LENGTH}자)",
        examples=["페트병 어떻게 버려요?"],
    )
    image_url: Optional[HttpUrl] = Field(
        default=None,
        description="분석할 이미지 URL (선택)",
        examples=["https://example.com/pet-bottle.jpg"],
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="응답 다양성 (0.0-2.0)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "이 페트병 어떻게 분리수거해요?",
                    "image_url": "https://example.com/pet-bottle.jpg",
                },
                {
                    "message": "유리병 버리는 방법 알려줘",
                },
            ]
        }
    }


# =============================================================================
# 응답 스키마
# =============================================================================


class DisposalStep(BaseModel):
    """배출 절차 단계"""

    step: int = Field(..., description="단계 번호")
    instruction: str = Field(..., description="단계별 안내")


class ChatMetadata(BaseModel):
    """응답 메타데이터"""

    pipeline_type: str = Field(
        ...,
        description="사용된 파이프라인 타입",
        examples=["image", "text"],
    )
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="처리 시각 (UTC)",
    )
    classification: Optional[Dict[str, Any]] = Field(
        default=None,
        description="분류 결과 (디버깅용)",
    )


class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답"""

    user_answer: str = Field(
        ...,
        description="사용자에게 보여줄 답변",
        examples=["페트병은 내용물을 비우고 라벨을 제거한 후 투명 페트병 수거함에 버려주세요."],
    )

    # 확장 필드 (선택적)
    disposal_steps: Optional[List[DisposalStep]] = Field(
        default=None,
        description="배출 절차 단계별 안내",
    )
    insufficiencies: Optional[List[str]] = Field(
        default=None,
        description="미흡한 항목 안내",
    )
    metadata: Optional[ChatMetadata] = Field(
        default=None,
        description="응답 메타데이터",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_answer": "페트병은 내용물을 비우고 라벨을 제거한 후 투명 페트병 수거함에 버려주세요.",
                    "disposal_steps": [
                        {"step": 1, "instruction": "내용물을 비워주세요"},
                        {"step": 2, "instruction": "라벨을 제거해주세요"},
                        {"step": 3, "instruction": "투명 페트병 수거함에 배출해주세요"},
                    ],
                    "insufficiencies": [],
                    "metadata": {
                        "pipeline_type": "image",
                        "processed_at": "2024-12-20T12:00:00Z",
                    },
                }
            ]
        }
    }


# =============================================================================
# 에러 응답 스키마
# =============================================================================


class ErrorDetail(BaseModel):
    """에러 상세 정보"""

    code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    field: Optional[str] = Field(default=None, description="관련 필드명")


class ErrorResponse(BaseModel):
    """에러 응답"""

    success: bool = Field(default=False, description="성공 여부")
    error: ErrorDetail = Field(..., description="에러 상세")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": {
                        "code": "PIPELINE_ERROR",
                        "message": "이미지 분석에 실패했습니다. 다시 시도해주세요.",
                    },
                }
            ]
        }
    }
