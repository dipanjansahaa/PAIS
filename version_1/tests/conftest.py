"""Shared pytest fixtures."""

import pytest_asyncio

from app.database.session import AsyncSessionFactory


@pytest_asyncio.fixture
async def db_session():
    """Provide an async database session for integration tests."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()