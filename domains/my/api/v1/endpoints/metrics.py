from fastapi import APIRouter, Depends

from domains.my.services.my import MyService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", summary="My service metrics")
async def metrics(service: MyService = Depends(MyService)):
    return await service.metrics()
