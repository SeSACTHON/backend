from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from domains.my.database.base import Base


class AuthUser(Base):
    """Read-only mirror of auth.users for profile hydration."""

    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(120))
    nickname: Mapped[Optional[str]] = mapped_column(String(120))
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(512))
