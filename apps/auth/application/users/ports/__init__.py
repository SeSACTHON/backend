"""Users domain ports.

사용자 관련 CRUD 및 외부 users 도메인 통신 포트입니다.
"""

from auth.application.users.ports.social_account_gateway import (
    SocialAccountGateway,
)
from auth.application.users.ports.users_command_gateway import UsersCommandGateway
from auth.application.users.ports.users_management_gateway import (
    OAuthUserResult,
    UsersManagementGateway,
)
from auth.application.users.ports.users_query_gateway import UsersQueryGateway

__all__ = [
    "UsersManagementGateway",
    "UsersQueryGateway",
    "UsersCommandGateway",
    "SocialAccountGateway",
    "OAuthUserResult",
]
