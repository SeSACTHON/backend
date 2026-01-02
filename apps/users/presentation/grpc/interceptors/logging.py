"""Logging Interceptor.

gRPC 요청/응답 로깅을 담당하는 인터셉터입니다.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import grpc

logger = logging.getLogger(__name__)


class LoggingInterceptor(grpc.aio.ServerInterceptor):
    """요청/응답 로깅 인터셉터.

    각 RPC 호출의 시작/종료와 소요 시간을 로깅합니다.
    """

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Any],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        """서비스 호출을 인터셉트합니다."""
        handler = await continuation(handler_call_details)

        if handler is None:
            return handler

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                self._wrap_unary_unary(handler.unary_unary, handler_call_details.method),
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )

        return handler

    def _wrap_unary_unary(
        self,
        behavior: Callable,
        method: str,
    ) -> Callable:
        """Unary-Unary RPC를 래핑합니다."""

        async def wrapper(
            request: Any,
            context: grpc.aio.ServicerContext,
        ) -> Any:
            start_time = time.perf_counter()

            logger.debug(
                "gRPC request started",
                extra={
                    "method": method,
                    "peer": context.peer(),
                },
            )

            try:
                response = await behavior(request, context)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    "gRPC request completed",
                    extra={
                        "method": method,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "status": "OK",
                    },
                )

                return response

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                logger.warning(
                    "gRPC request failed",
                    extra={
                        "method": method,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "error_type": type(e).__name__,
                    },
                )

                raise

        return wrapper
