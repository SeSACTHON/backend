"""LoginAudit ORM Mapping."""

from sqlalchemy import Table, Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from apps.auth.infrastructure.persistence_postgres.registry import mapper_registry


login_audits_table = Table(
    "login_audits",
    mapper_registry.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("provider", String(32), nullable=False),
    Column("jti", String(64), nullable=False),
    Column("login_ip", String(64)),
    Column("user_agent", String(512)),
    Column("issued_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    schema="auth",
)


def start_login_audit_mapper() -> None:
    """LoginAudit 매퍼 시작."""
    from apps.auth.domain.entities.login_audit import LoginAudit

    if hasattr(LoginAudit, "__mapper__"):
        return

    mapper_registry.map_imperatively(
        LoginAudit,
        login_audits_table,
    )
