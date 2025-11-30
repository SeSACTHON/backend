from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html

router = APIRouter(prefix="/images", include_in_schema=False)


@router.get("/docs", summary="Image API Swagger UI")
async def image_swagger_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Image API Docs",
    )
