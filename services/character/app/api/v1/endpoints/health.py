from app.api.v1.router import health_router

SERVICE_NAME = "character"


@health_router.get("/health")
async def health():
    return {"status": "healthy", "service": f"{SERVICE_NAME}-api"}


@health_router.get("/ready")
async def readiness():
    return {"status": "ready", "service": f"{SERVICE_NAME}-api"}
