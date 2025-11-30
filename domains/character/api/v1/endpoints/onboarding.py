from fastapi import APIRouter, Depends

from domains.character.schemas.catalog import (
    CharacterAcquireResponse,
    DefaultCharacterGrantRequest,
)
from domains.character.services.character import CharacterService
from domains.character.api.dependencies import service_token_dependency

router = APIRouter(
    prefix="/internal/characters",
    tags=["character-onboarding"],
    dependencies=[Depends(service_token_dependency)],
)


@router.post(
    "/default",
    response_model=CharacterAcquireResponse,
    summary="Grant the default character to a user during onboarding",
)
async def grant_default_character(
    payload: DefaultCharacterGrantRequest,
    service: CharacterService = Depends(),
):
    return await service.grant_default_character(payload.user_id)
