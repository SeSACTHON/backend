"""Health/Readiness probe endpoints (로그 제외 - 노이즈 방지)."""

from fastapi import APIRouter

from domains.chat.core.constants import SERVICE_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness probe - 서비스 생존 확인"""
    return {"status": "healthy", "service": SERVICE_NAME}


@router.get("/ready")
async def readiness():
    """Readiness probe - 트래픽 수신 준비 확인"""
    return {"status": "ready", "service": SERVICE_NAME}
