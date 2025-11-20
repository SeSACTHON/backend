from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, UUID as SAUUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.character import Character


class UserCharacter(Base):
    __tablename__ = "user_characters"
    __table_args__ = (
        Index("ix_user_characters_user_id", "user_id"),
        Index("ix_user_characters_character_id", "character_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        SAUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(SAUUID(as_uuid=True), nullable=False)
    character_id: Mapped[uuid.UUID] = mapped_column(
        SAUUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    affection_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    classification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    character: Mapped[Character] = relationship(back_populates="user_characters")
