"""SQLAlchemy Adapters for PostgreSQL.

Port 구현체들을 제공합니다.
"""

from auth.infrastructure.persistence_postgres.adapters.flusher_sqla import (
    SqlaFlusher,
)
from auth.infrastructure.persistence_postgres.adapters.login_audit_gateway_sqla import (
    SqlaLoginAuditGateway,
)
from auth.infrastructure.persistence_postgres.adapters.social_account_query_gateway_sqla import (
    SqlaSocialAccountQueryGateway,
)
from auth.infrastructure.persistence_postgres.adapters.transaction_manager_sqla import (
    SqlaTransactionManager,
)
from auth.infrastructure.persistence_postgres.adapters.users_command_gateway_sqla import (
    SqlaUsersCommandGateway,
)
from auth.infrastructure.persistence_postgres.adapters.users_query_gateway_sqla import (
    SqlaUsersQueryGateway,
)

__all__ = [
    "SqlaFlusher",
    "SqlaLoginAuditGateway",
    "SqlaSocialAccountQueryGateway",
    "SqlaTransactionManager",
    "SqlaUsersCommandGateway",
    "SqlaUsersQueryGateway",
]
