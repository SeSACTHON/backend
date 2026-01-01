"""Auth User ORM Mapping (임시).

Phase 1: users gRPC가 auth 스키마에 접근하기 위한 매핑.
Phase 2: users.users 스키마로 마이그레이션 후 제거 예정.

Note: 이 매핑은 도메인 경계를 임시로 넘는 것이며,
      데이터 소유권 통합 후 제거됩니다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import registry, relationship

# auth 스키마용 별도 registry
auth_metadata = MetaData(schema="auth")
auth_mapper_registry = registry(metadata=auth_metadata)


# auth.users 테이블
auth_users_table = Table(
    "users",
    auth_metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("username", String(120), nullable=True),
    Column("nickname", String(120), nullable=True),
    Column("profile_image_url", String(500), nullable=True),
    Column("phone_number", String(32), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True), nullable=True),
)


# auth.user_social_accounts 테이블
auth_user_social_accounts_table = Table(
    "user_social_accounts",
    auth_metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("provider", String(32), nullable=False),
    Column("provider_user_id", String(255), nullable=False),
    Column("email", String(320), nullable=True),
    Column("last_login_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("provider", "provider_user_id", name="uq_user_social_accounts_identity"),
)


# ORM 모델 클래스 (users 도메인 전용)
class AuthUserModel:
    """auth.users 테이블 모델 (임시)."""

    id: UUID
    username: str | None
    nickname: str | None
    profile_image_url: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
    social_accounts: list["AuthSocialAccountModel"]


class AuthSocialAccountModel:
    """auth.user_social_accounts 테이블 모델 (임시)."""

    id: UUID
    user_id: UUID
    provider: str
    provider_user_id: str
    email: str | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


def start_auth_mappers() -> None:
    """auth 스키마 매퍼 시작."""
    if hasattr(AuthUserModel, "__mapper__"):
        return

    auth_mapper_registry.map_imperatively(
        AuthUserModel,
        auth_users_table,
        properties={
            "social_accounts": relationship(
                AuthSocialAccountModel,
                back_populates="user",
                lazy="selectin",
            ),
        },
    )

    auth_mapper_registry.map_imperatively(
        AuthSocialAccountModel,
        auth_user_social_accounts_table,
        properties={
            "user": relationship(
                AuthUserModel,
                back_populates="social_accounts",
            ),
        },
    )


__all__ = [
    "AuthUserModel",
    "AuthSocialAccountModel",
    "auth_users_table",
    "auth_user_social_accounts_table",
    "start_auth_mappers",
]
