"""Error Handler Interceptor.

예외를 gRPC status code로 변환하는 인터셉터입니다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import grpc

logger = logging.getLogger(__name__)


class ErrorHandlerInterceptor(grpc.aio.ServerInterceptor):
    """예외를 gRPC status로 변환하는 인터셉터.

    Servicer에서 발생하는 예외를 캐치하여 적절한 gRPC status code로 변환합니다.
    이를 통해 Servicer는 예외 처리 보일러플레이트 없이 비즈니스 로직에 집중할 수 있습니다.

    매핑 규칙:
        - ValueError → INVALID_ARGUMENT
        - KeyError → NOT_FOUND
        - PermissionError → PERMISSION_DENIED
        - NotImplementedError → UNIMPLEMENTED
        - Exception → INTERNAL
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
                self._wrap_unary_unary(handler.unary_unary),
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )

        # 다른 RPC 타입은 그대로 반환 (streaming 등)
        return handler

    def _wrap_unary_unary(
        self,
        behavior: Callable,
    ) -> Callable:
        """Unary-Unary RPC를 래핑합니다."""

        async def wrapper(
            request: Any,
            context: grpc.aio.ServicerContext,
        ) -> Any:
            try:
                return await behavior(request, context)
            except ValueError as e:
                logger.warning(
                    "Invalid argument",
                    extra={
                        "error": str(e),
                        "method": context.method(),
                    },
                )
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            except KeyError as e:
                logger.warning(
                    "Resource not found",
                    extra={
                        "error": str(e),
                        "method": context.method(),
                    },
                )
                await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            except PermissionError as e:
                logger.warning(
                    "Permission denied",
                    extra={
                        "error": str(e),
                        "method": context.method(),
                    },
                )
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            except NotImplementedError as e:
                logger.warning(
                    "Not implemented",
                    extra={
                        "error": str(e),
                        "method": context.method(),
                    },
                )
                await context.abort(grpc.StatusCode.UNIMPLEMENTED, str(e))
            except Exception:
                logger.exception(
                    "Internal error",
                    extra={"method": context.method()},
                )
                await context.abort(grpc.StatusCode.INTERNAL, "Internal server error")

        return wrapper
