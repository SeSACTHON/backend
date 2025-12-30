"""Health Check Controller."""

from fastapi import APIRouter

from apps.auth.presentation.http.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """서비스 상태 확인."""
    return HealthResponse(status="healthy", version="2.0.0")


@router.get("/ping")
async def ping() -> dict:
    """간단한 ping 엔드포인트."""
    return {"ping": "pong"}
