from fastapi import APIRouter, Depends, HTTPException, status

from domains._shared.security import TokenPayload

from domains.image.api.v1.dependencies import get_image_service
from domains.image.schemas.image import (
    ImageChannel,
    ImageUploadCallbackRequest,
    ImageUploadFinalizeResponse,
    ImageUploadRequest,
    ImageUploadResponse,
)
from domains.image.services.image import ImageService
from domains.image.services.image import (
    PendingUploadChannelMismatchError,
    PendingUploadNotFoundError,
    PendingUploadPermissionDeniedError,
)
from domains.image.security import access_token_dependency

router = APIRouter(prefix="/images", tags=["images"])


@router.post(
    "/{channel}",
    response_model=ImageUploadResponse,
    summary="Create presigned upload URL",
)
async def create_upload_url(
    channel: ImageChannel,
    payload: ImageUploadRequest,
    service: ImageService = Depends(get_image_service),
    token: TokenPayload = Depends(access_token_dependency),
):
    token_user_id = str(token.user_id)
    if payload.uploader_id and payload.uploader_id != token_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Uploader mismatch",
        )
    return await service.create_upload_url(
        channel,
        payload,
        uploader_id=token_user_id,
    )


@router.post(
    "/{channel}/callback",
    response_model=ImageUploadFinalizeResponse,
    summary="Confirm upload completion",
)
async def finalize_upload(
    channel: ImageChannel,
    payload: ImageUploadCallbackRequest,
    service: ImageService = Depends(get_image_service),
    token: TokenPayload = Depends(access_token_dependency),
):
    try:
        return await service.finalize_upload(
            channel,
            payload,
            uploader_id=str(token.user_id),
        )
    except PendingUploadNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found or expired",
        ) from None
    except PendingUploadChannelMismatchError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel does not match the original upload request",
        ) from None
    except PendingUploadPermissionDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Uploader mismatch",
        ) from None
