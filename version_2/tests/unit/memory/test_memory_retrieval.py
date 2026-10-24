"""Tests for personal memory retrieval."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from app.database.models.memory import Memory
from app.memory.service import MemoryService


@pytest.fixture
def service() -> MemoryService:
    return MemoryService()


def make_memory(
    *,
    user_id=None,
    content: str,
    memory_type: str = "fact",
    confidence: float | None = 0.8,
    created_at: datetime | None = None,
) -> Memory:
    """Create an in-memory Memory model for retrieval tests."""
    memory = Memory(
        user_id=user_id or uuid4(),
        memory_type=memory_type,
        content=content,
        normalized_content=content.casefold(),
        status="active",
        confidence=confidence,
    )
    memory.created_at = created_at or datetime.now(UTC)
    memory.id = uuid4()
    memory.sources = []
    return memory


def make_session(memories: list[Memory]) -> AsyncMock:
    """Return a session whose scalar query yields the supplied memories."""
    result = Mock()
    result.all.return_value = memories

    session = AsyncMock()
    session.scalars = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_retrieve_memories_ranks_relevant_content(
    service: MemoryService,
) -> None:
    user_id = uuid4()

    unrelated = make_memory(
        user_id=user_id,
        content="The office is located in Kolkata.",
    )
    relevant = make_memory(
        user_id=user_id,
        content="I prefer Python for backend development.",
    )
    exact_phrase = make_memory(
        user_id=user_id,
        content="I prefer Python.",
    )

    session = make_session([unrelated, relevant, exact_phrase])

    results = await service.retrieve_memories(
        session,
        user_id=user_id,
        query="prefer Python",
    )

    assert [memory.id for memory in results] == [
        exact_phrase.id,
        relevant.id,
    ]


@pytest.mark.asyncio
async def test_retrieve_memories_limits_results(
    service: MemoryService,
) -> None:
    user_id = uuid4()
    memories = [
        make_memory(
            user_id=user_id,
            content=f"Python preference number {index}",
        )
        for index in range(5)
    ]
    session = make_session(memories)

    results = await service.retrieve_memories(
        session,
        user_id=user_id,
        query="Python preference",
        limit=2,
    )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_retrieve_memories_without_query_returns_recent_first(
    service: MemoryService,
) -> None:
    user_id = uuid4()
    now = datetime.now(UTC)

    older = make_memory(
        user_id=user_id,
        content="Older preference",
        created_at=now - timedelta(days=2),
    )
    newer = make_memory(
        user_id=user_id,
        content="Newer preference",
        created_at=now - timedelta(days=1),
    )

    session = make_session([older, newer])

    results = await service.retrieve_memories(
        session,
        user_id=user_id,
    )

    assert [memory.id for memory in results] == [
        newer.id,
        older.id,
    ]


@pytest.mark.asyncio
async def test_retrieve_memories_rejects_invalid_limit(
    service: MemoryService,
) -> None:
    session = AsyncMock()

    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.retrieve_memories(
            session,
            user_id=uuid4(),
            limit=0,
        )

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_memories_rejects_invalid_memory_type(
    service: MemoryService,
) -> None:
    session = AsyncMock()

    with pytest.raises(ValueError, match="Unsupported memory type"):
        await service.retrieve_memories(
            session,
            user_id=uuid4(),
            memory_types={"unsupported"},  # type: ignore[arg-type]
        )

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_memories_returns_empty_when_no_matches(
    service: MemoryService,
) -> None:
    session = make_session(
        [
            make_memory(
                content="I prefer Python.",
            )
        ]
    )

    results = await service.retrieve_memories(
        session,
        user_id=uuid4(),
        query="gardening",
    )

    assert results == []
