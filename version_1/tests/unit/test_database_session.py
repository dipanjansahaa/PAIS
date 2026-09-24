"""Unit tests for database session infrastructure."""

from app.database.session import AsyncSessionFactory, engine


def test_engine_is_configured() -> None:
    assert engine is not None
    assert engine.url.drivername == "postgresql+asyncpg"


def test_session_factory_is_configured() -> None:
    assert AsyncSessionFactory.kw["expire_on_commit"] is False
    assert AsyncSessionFactory.kw["autoflush"] is False
