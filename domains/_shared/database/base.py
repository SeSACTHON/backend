"""Shared SQLAlchemy Declarative Base.

모든 도메인에서 공통으로 사용하는 SQLAlchemy Base 클래스입니다.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all domain models."""

    pass
