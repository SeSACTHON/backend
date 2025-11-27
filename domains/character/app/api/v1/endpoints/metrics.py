from fastapi import APIRouter, Depends

from domains.character.app.services.character import CharacterService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", summary="Character service metrics snapshot")
async def metrics(service: CharacterService = Depends()):
    return await service.metrics()
