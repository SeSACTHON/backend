from fastapi import Depends

from app.api.v1.router import metrics_router
from app.service import CharacterService


@metrics_router.get("/", summary="Character service metrics snapshot")
async def metrics(service: CharacterService = Depends()):
    return await service.metrics()
