from fastapi import APIRouter, Depends

from app.dependencies.security import access_token_dependency

character_router = APIRouter(
    prefix="/character",
    tags=["character"],
    dependencies=[Depends(access_token_dependency)],
)

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])

api_router = APIRouter()
api_router.include_router(character_router)
api_router.include_router(metrics_router)

health_router = APIRouter(tags=["health"])

__all__ = ["api_router", "character_router", "health_router", "metrics_router"]
