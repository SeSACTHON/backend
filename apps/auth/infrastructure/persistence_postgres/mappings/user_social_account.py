"""UserSocialAccount ORM Mapping."""

from sqlalchemy import Table, Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from apps.auth.infrastructure.persistence_postgres.registry import mapper_registry


user_social_accounts_table = Table(
    "user_social_accounts",
    mapper_registry.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("provider", String(32), nullable=False, index=True),
    Column("provider_user_id", String(255), nullable=False, index=True),
    Column("email", String(320)),
    Column("last_login_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("provider", "provider_user_id", name="uq_user_social_accounts_identity"),
    schema="auth",
)


def start_social_account_mapper() -> None:
    """UserSocialAccount 매퍼 시작."""
    from apps.auth.domain.entities.user_social_account import UserSocialAccount

    if hasattr(UserSocialAccount, "__mapper__"):
        return

    mapper_registry.map_imperatively(
        UserSocialAccount,
        user_social_accounts_table,
    )
