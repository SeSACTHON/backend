"""Gateway Exceptions."""

from apps.auth.application.common.exceptions.base import ApplicationError


class GatewayError(ApplicationError):
    """Gateway 오류 베이스 클래스."""

    pass


class DataMapperError(GatewayError):
    """데이터 매퍼(Repository) 오류."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        super().__init__(f"Data mapper error during {operation}: {reason}")
