"""Database-backed reliability tests for personal-memory retrieval."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.database.models.memory import Memory, MemorySource
from app.database.models.user import User
from app.memory.service import MemoryService

pytestmark = pytest.mark.integration


async def create_user(db_session, *, label: str) -> User:
    user = User(
        email=f"{label}-{uuid4()}@pais.local",
        display_name=f"Memory Evaluation User {label}",
    )
    db_session.add(user)
    await db_session.flush()
    return user


def create_memory(
    *,
    user_id,
    content: str,
    status: str = "active",
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> Memory:
    return Memory(
        user_id=user_id,
        memory_type="preference",
        content=content,
        normalized_content=" ".join(content.casefold().split()),
        status=status,
        confidence=0.9,
        valid_from=valid_from,
        valid_until=valid_until,
    )


@pytest.mark.asyncio
async def test_retrieval_enforces_user_lifecycle_and_validity(
    db_session,
) -> None:
    """Return only the user's active memories valid at the requested time."""
    service = MemoryService()
    now = datetime.now(UTC)
    user = await create_user(db_session, label="primary")
    other_user = await create_user(db_session, label="other")

    valid_memory = create_memory(
        user_id=user.id,
        content="I prefer Python for backend development.",
    )
    future_memory = create_memory(
        user_id=user.id,
        content="I prefer Python for future backend development.",
        valid_from=now + timedelta(days=1),
    )
    expired_memory = create_memory(
        user_id=user.id,
        content="I prefer Python for legacy backend development.",
        valid_until=now,
    )
    superseded_memory = create_memory(
        user_id=user.id,
        content="I prefer Python for older backend development.",
        status="superseded",
    )
    other_users_memory = create_memory(
        user_id=other_user.id,
        content="I prefer Python for backend development.",
    )

    db_session.add_all(
        [
            valid_memory,
            future_memory,
            expired_memory,
            superseded_memory,
            other_users_memory,
        ]
    )
    await db_session.flush()

    results = await service.retrieve_memories(
        db_session,
        user_id=user.id,
        query="prefer Python backend development",
        as_of=now,
    )

    assert [memory.id for memory in results] == [valid_memory.id]


@pytest.mark.asyncio
async def test_retrieval_preserves_memory_source_provenance(
    db_session,
) -> None:
    """Retrieved memories include their persisted provenance records."""
    service = MemoryService()
    user = await create_user(db_session, label="provenance")

    memory = create_memory(
        user_id=user.id,
        content="I prefer Python for backend development.",
    )
    source = MemorySource(
        memory=memory,
        source_kind="manual",
        source_reference="evaluation-fixture",
        evidence_text="The user explicitly stated this preference.",
    )

    db_session.add_all([memory, source])
    await db_session.flush()

    results = await service.retrieve_memories(
        db_session,
        user_id=user.id,
        query="prefer Python backend development",
    )

    assert len(results) == 1
    assert results[0].id == memory.id
    assert len(results[0].sources) == 1

    retrieved_source = results[0].sources[0]
    assert retrieved_source.source_kind == "manual"
    assert retrieved_source.source_reference == "evaluation-fixture"
    assert retrieved_source.evidence_text == "The user explicitly stated this preference."
