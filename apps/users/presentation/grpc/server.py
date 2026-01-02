"""gRPC server for Users service.

auth 도메인에서 호출하는 사용자 관련 gRPC 서비스입니다.

Usage:
    python -m apps.users.presentation.grpc.server
"""

from __future__ import annotations

import asyncio
import logging
import signal
from concurrent import futures

import grpc

from apps.users.infrastructure.persistence_postgres.mappings import start_mappers
from apps.users.infrastructure.persistence_postgres.session import (
    async_session_factory,
)
from apps.users.presentation.grpc.interceptors import (
    ErrorHandlerInterceptor,
    LoggingInterceptor,
)
from apps.users.presentation.grpc.protos import add_UsersServiceServicer_to_server
from apps.users.presentation.grpc.servicers import UsersServicer
from apps.users.setup.config import get_settings
from apps.users.setup.dependencies import GrpcUseCaseFactory
from apps.users.setup.logging import setup_logging

logger = logging.getLogger(__name__)


async def serve() -> None:
    """Start the gRPC server with graceful shutdown support."""
    settings = get_settings()

    # 로깅 설정
    setup_logging()

    # ORM 매퍼 초기화
    start_mappers()

    # UseCase 팩토리 생성
    use_case_factory = GrpcUseCaseFactory(async_session_factory)

    # 인터셉터 설정 (순서 중요: 먼저 등록된 것이 먼저 실행)
    interceptors = [
        LoggingInterceptor(),      # 1. 요청/응답 로깅
        ErrorHandlerInterceptor(), # 2. 예외 → gRPC status 변환
    ]

    # gRPC 서버 생성
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=settings.grpc_max_workers),
        interceptors=interceptors,
    )

    # Servicer 등록 (Thin Adapter)
    add_UsersServiceServicer_to_server(
        UsersServicer(
            session_factory=async_session_factory,
            use_case_factory=use_case_factory,
        ),
        server,
    )

    # 포트 바인딩
    listen_addr = f"[::]:{settings.grpc_server_port}"
    server.add_insecure_port(listen_addr)

    logger.info(
        "Starting Users gRPC server",
        extra={
            "address": listen_addr,
            "max_workers": settings.grpc_max_workers,
            "environment": settings.environment,
            "interceptors": [type(i).__name__ for i in interceptors],
        },
    )

    await server.start()

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info("Received shutdown signal", extra={"signal": sig.name})
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal, sig)

    logger.info("Users gRPC server started, waiting for requests")
    await stop_event.wait()

    logger.info("Stopping gRPC server gracefully")
    await server.stop(grace=5)
    logger.info("Users gRPC server stopped")


if __name__ == "__main__":
    asyncio.run(serve())
