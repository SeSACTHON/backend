"""Common HTTP Schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health Check 응답."""

    status: str = Field(default="healthy", description="서비스 상태")
    version: str = Field(default="2.0.0", description="API 버전")


class ErrorResponse(BaseModel):
    """에러 응답."""

    detail: str = Field(..., description="에러 메시지")
    code: str | None = Field(None, description="에러 코드")
