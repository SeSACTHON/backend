"""Application Queries.

CQRS 패턴의 Query 측을 담당합니다.
"""

from apps.auth.application.queries.validate_token import ValidateTokenQueryService

__all__ = ["ValidateTokenQueryService"]
