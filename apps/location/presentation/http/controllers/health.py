"""Health Check Controller."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """헬스체크 엔드포인트."""
    return {"status": "healthy", "service": "location-api"}


@router.get("/ping")
async def ping() -> dict:
    """Ping 엔드포인트."""
    return {"pong": True}
