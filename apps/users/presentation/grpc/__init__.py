"""gRPC presentation layer for users domain.

프로토콜:
    - gRPC: auth 도메인에서 호출하는 사용자 관련 서비스

폴더 구조:
    - protos/: 생성된 protobuf 파일 (pb2, pb2_grpc)
    - servicers/: gRPC servicer (thin adapter)
    - interceptors/: 횡단 관심사 (로깅, 에러 핸들링)
    - server.py: gRPC 서버 부팅 코드
"""

from apps.users.presentation.grpc import protos
from apps.users.presentation.grpc.interceptors import (
    ErrorHandlerInterceptor,
    LoggingInterceptor,
)
from apps.users.presentation.grpc.servicers import UsersServicer

__all__ = [
    "protos",
    "UsersServicer",
    "ErrorHandlerInterceptor",
    "LoggingInterceptor",
]
