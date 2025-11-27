from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from domains.my.database.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="ux_users_provider_identity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
