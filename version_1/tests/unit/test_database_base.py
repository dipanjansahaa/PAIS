"""Unit tests for the SQLAlchemy database base."""

from app.database.base import Base


def test_base_metadata_is_available() -> None:
    assert Base.metadata is not None
    assert len(Base.metadata.tables) == 0
