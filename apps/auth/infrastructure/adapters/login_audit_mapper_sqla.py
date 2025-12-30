"""SQLAlchemy LoginAudit Mapper.

LoginAuditGateway의 구현체입니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.auth.domain.entities.login_audit import LoginAudit

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlaLoginAuditMapper:
    """SQLAlchemy 기반 LoginAudit Gateway.

    LoginAuditGateway 구현체.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    def add(self, login_audit: LoginAudit) -> None:
        """로그인 감사 기록 추가."""
        self._session.add(login_audit)
