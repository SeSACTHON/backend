from fastapi import Depends, status

from app.api.v1.router import character_router
from app.service.user_character import UserCharacterService, get_user_character_service
from app.schemas import (
    CharacterRewardRequest,
    CharacterRewardResult,
    UserCharacterWithDetail,
)


@character_router.post(
    "/ownerships",
    response_model=CharacterRewardResult,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a character instance based on waste classification",
)
async def grant_character(
    payload: CharacterRewardRequest,
    service: UserCharacterService = Depends(get_user_character_service),
):
    return await service.grant_character(payload)


@character_router.get(
    "/me",
    response_model=list[UserCharacterWithDetail],
    summary="List characters owned by the current user",
)
async def owned_characters(service: UserCharacterService = Depends(get_user_character_service)):
    return await service.owned_characters()
