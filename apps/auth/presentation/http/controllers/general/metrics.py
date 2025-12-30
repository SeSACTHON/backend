"""Metrics Controller."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/metrics")
async def get_metrics() -> dict:
    """메트릭스 조회.

    Prometheus 포맷은 별도 미들웨어에서 처리합니다.
    """
    return {
        "service": "auth-api",
        "version": "2.0.0",
        "architecture": "clean-architecture",
    }
