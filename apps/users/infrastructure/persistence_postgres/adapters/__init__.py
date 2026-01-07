"""Infrastructure adapters implementing application ports."""

from users.infrastructure.persistence_postgres.adapters.identity_gateway_sqla import (
    SqlaIdentityCommandGateway,
    SqlaIdentityQueryGateway,
)
from users.infrastructure.persistence_postgres.adapters.social_account_gateway_sqla import (
    SqlaSocialAccountQueryGateway,
)
from users.infrastructure.persistence_postgres.adapters.transaction_manager_sqla import (
    SqlaTransactionManager,
)
from users.infrastructure.persistence_postgres.adapters.users_character_gateway_sqla import (
    SqlaUsersCharacterQueryGateway,
)
from users.infrastructure.persistence_postgres.adapters.users_gateway_sqla import (
    SqlaUsersCommandGateway,
    SqlaUsersQueryGateway,
)

__all__ = [
    "SqlaUsersQueryGateway",
    "SqlaUsersCommandGateway",
    "SqlaUsersCharacterQueryGateway",
    "SqlaTransactionManager",
    "SqlaSocialAccountQueryGateway",
    "SqlaIdentityQueryGateway",
    "SqlaIdentityCommandGateway",
]
