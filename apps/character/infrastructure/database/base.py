"""SQLAlchemy Declarative Base.

Character 서비스 전용 - domains 의존성 제거.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for Character domain models."""

    pass
