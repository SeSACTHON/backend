from fastapi import APIRouter

from domains.my.api.v1.endpoints import characters, health, metrics, profile

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(profile.router)
api_router.include_router(metrics.router)
api_router.include_router(characters.router)

health_router = APIRouter()
health_router.include_router(health.router)

__all__ = ["api_router", "health_router"]
