from fastapi import APIRouter, Depends

from domains.character.schemas.character import CharacterProfile
from domains.character.services.character import CharacterService

router = APIRouter(prefix="/character", tags=["character"])


@router.get(
    "/catalog",
    response_model=list[CharacterProfile],
    summary="Available character catalog",
)
async def catalog(service: CharacterService = Depends()):
    return await service.catalog()
