"""SQLAlchemy declarative base and shared database metadata."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all PAIS SQLAlchemy models."""

    pass
