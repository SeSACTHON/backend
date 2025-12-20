"""Chat API Application

FastAPI 애플리케이션 설정 및 미들웨어 구성
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from domains.chat.api.v1.routers import api_router, health_router
from domains.chat.core.config import get_settings
from domains.chat.core.constants import (
    DEFAULT_ENVIRONMENT,
    ENV_KEY_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
)
from domains.chat.core.logging import configure_logging
from domains.chat.core.tracing import (
    configure_tracing,
    instrument_fastapi,
    instrument_httpx,
    shutdown_tracing,
)
from domains.chat.metrics import register_metrics

# =============================================================================
# 초기화
# =============================================================================

# 구조화된 로깅 설정 (ECS JSON 포맷)
configure_logging()

# OpenTelemetry 분산 트레이싱 설정
environment = os.getenv(ENV_KEY_ENVIRONMENT, DEFAULT_ENVIRONMENT)
configure_tracing(
    service_name=SERVICE_NAME,
    service_version=SERVICE_VERSION,
    environment=environment,
)

# 글로벌 instrumentation
instrument_httpx()


# =============================================================================
# Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    yield
    shutdown_tracing()


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성

    Returns:
        FastAPI: 구성된 애플리케이션 인스턴스
    """
    settings = get_settings()

    app = FastAPI(
        title="Chat API",
        description="Conversational assistant for recycling topics",
        version=SERVICE_VERSION,
        docs_url="/api/v1/chat/docs",
        openapi_url="/api/v1/chat/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS 미들웨어 (설정에서 origins 가져옴)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # OpenTelemetry FastAPI instrumentation
    instrument_fastapi(app)

    # 라우터 등록
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")

    # Prometheus 메트릭 등록
    register_metrics(app)

    return app


# =============================================================================
# Application Instance
# =============================================================================

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
