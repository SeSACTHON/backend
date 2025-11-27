from fastapi import APIRouter, Depends, Path

from domains.my.schemas import UserProfile, UserUpdate
from domains.my.services.my import MyService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserProfile, summary="Get user profile")
async def get_user(user_id: int = Path(..., gt=0), service: MyService = Depends(MyService)):
    return await service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserProfile, summary="Update profile")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    service: MyService = Depends(MyService),
):
    return await service.update_user(user_id, payload)


@router.delete("/{user_id}", summary="Delete user")
async def delete_user(user_id: int, service: MyService = Depends(MyService)):
    await service.delete_user(user_id)
    return {"message": f"user {user_id} deleted"}
