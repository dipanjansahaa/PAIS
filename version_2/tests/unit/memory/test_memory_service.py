"""Tests for the persistent memory service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from app.database.models.memory import Memory
from app.memory.service import MemoryService


@pytest.fixture
def service() -> MemoryService:
    return MemoryService()


def test_normalize_content(service: MemoryService) -> None:
    assert service.normalize_content(
        "  I   prefer   Python  "
    ) == "i prefer python"


@pytest.mark.parametrize(
    "content",
    ["", "   ", "\n\t"],
)
def test_normalize_empty_content(
    service: MemoryService,
    content: str,
) -> None:
    assert service.normalize_content(content) == ""


@pytest.mark.asyncio
async def test_create_memory_rejects_empty_content(
    service: MemoryService,
) -> None:
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    with pytest.raises(ValueError, match="must not be empty"):
        await service.create_memory(
            session,
            user_id=uuid4(),
            memory_type="fact",
            content="   ",
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_memory_rejects_invalid_type(
    service: MemoryService,
) -> None:
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    with pytest.raises(ValueError, match="Unsupported memory type"):
        await service.create_memory(
            session,
            user_id=uuid4(),
            memory_type="invalid",  # type: ignore[arg-type]
            content="The sky is blue.",
        )


@pytest.mark.asyncio
async def test_create_memory_rejects_invalid_confidence(
    service: MemoryService,
) -> None:
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    with pytest.raises(ValueError, match="Confidence"):
        await service.create_memory(
            session,
            user_id=uuid4(),
            memory_type="fact",
            content="The sky is blue.",
            confidence=1.5,
        )


@pytest.mark.asyncio
async def test_create_memory_rejects_invalid_validity_range(
    service: MemoryService,
) -> None:
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    now = datetime.now(UTC)

    with pytest.raises(ValueError, match="valid_until"):
        await service.create_memory(
            session,
            user_id=uuid4(),
            memory_type="fact",
            content="The sky is blue.",
            valid_from=now,
            valid_until=now - timedelta(seconds=1),
        )


@pytest.mark.asyncio
async def test_create_memory_persists_memory_and_source(
    service: MemoryService,
) -> None:
    user_id = uuid4()
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    # No document or chunk source is supplied, so ownership validation
    # doesn't need to query the database.
    session.scalar = AsyncMock(return_value=None)

    # First scalar query: no matching active memory.
    # AsyncMock.scalar is used by duplicate lookup.
    session.scalar.return_value = None

    result = await service.create_memory(
        session,
        user_id=user_id,
        memory_type="preference",
        content="  I prefer Python  ",
        confidence=0.9,
        source_kind="manual",
    )

    assert isinstance(result, Memory)
    assert result.user_id == user_id
    assert result.memory_type == "preference"
    assert result.content == "I prefer Python"
    assert result.normalized_content == "i prefer python"
    assert result.confidence == 0.9
    assert result.last_confirmed_at is not None

    assert session.add.call_count == 2
    assert session.flush.await_count == 2


@pytest.mark.asyncio
async def test_create_memory_reuses_existing_active_memory(
    service: MemoryService,
) -> None:
    user_id = uuid4()
    existing = Memory(
        user_id=user_id,
        memory_type="preference",
        content="I prefer Python",
        normalized_content="i prefer python",
        status="active",
    )

    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    session.scalar = AsyncMock(return_value=existing)

    result = await service.create_memory(
        session,
        user_id=user_id,
        memory_type="preference",
        content="  I   prefer Python ",
    )

    assert result is existing
    assert existing.last_confirmed_at is not None
    session.add.assert_not_called()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_memory_validates_document_ownership(
    service: MemoryService,
) -> None:
    user_id = uuid4()
    document_id = uuid4()
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()

    # Document lookup returns no matching document for this user.
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="does not belong to the user"):
        await service.create_memory(
            session,
            user_id=user_id,
            memory_type="fact",
            content="A fact",
            document_id=document_id,
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_supersede_memory_updates_both_records():
    service = MemoryService()
    user_id = uuid4()
    old_memory_id = uuid4()
    replacement_id = uuid4()

    old_memory = Mock(spec=Memory)
    old_memory.id = old_memory_id
    old_memory.user_id = user_id
    old_memory.status = "active"
    old_memory.memory_type = "preference"

    replacement = Mock(spec=Memory)
    replacement.id = replacement_id
    replacement.user_id = user_id
    replacement.status = "active"
    replacement.memory_type = "preference"
    replacement.supersedes_id = None

    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[old_memory, replacement])
    session.flush = AsyncMock()

    result = await service.supersede_memory(
        session,
        user_id=user_id,
        old_memory_id=old_memory_id,
        replacement_memory_id=replacement_id,
    )

    assert result is replacement
    assert old_memory.status == "superseded"
    assert replacement.supersedes_id == old_memory_id
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_supersede_memory_rejects_different_memory_types():
    service = MemoryService()
    user_id = uuid4()

    old_memory = Mock(spec=Memory)
    old_memory.id = uuid4()
    old_memory.user_id = user_id
    old_memory.status = "active"
    old_memory.memory_type = "preference"

    replacement = Mock(spec=Memory)
    replacement.id = uuid4()
    replacement.user_id = user_id
    replacement.status = "active"
    replacement.memory_type = "goal"
    replacement.supersedes_id = None

    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[old_memory, replacement])
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="same type"):
        await service.supersede_memory(
            session,
            user_id=user_id,
            old_memory_id=old_memory.id,
            replacement_memory_id=replacement.id,
        )

    assert old_memory.status == "active"
    assert replacement.supersedes_id is None
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_expire_outdated_memories_expires_only_matching_records():
    service = MemoryService()
    user_id = uuid4()
    now = datetime.now(UTC)

    expired_memory = Mock(spec=Memory)
    expired_memory.status = "active"
    expired_memory.valid_until = now - timedelta(days=1)

    result_proxy = Mock()
    result_proxy.all.return_value = [expired_memory]

    session = AsyncMock()
    session.scalars = AsyncMock(return_value=result_proxy)
    session.flush = AsyncMock()

    count = await service.expire_outdated_memories(
        session,
        user_id=user_id,
        as_of=now,
    )

    assert count == 1
    assert expired_memory.status == "expired"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_expire_outdated_memories_does_not_flush_when_none_expire():
    service = MemoryService()

    result_proxy = Mock()
    result_proxy.all.return_value = []

    session = AsyncMock()
    session.scalars = AsyncMock(return_value=result_proxy)
    session.flush = AsyncMock()

    count = await service.expire_outdated_memories(
        session,
        user_id=uuid4(),
        as_of=datetime.now(UTC),
    )

    assert count == 0
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_memory_preserves_history_and_links_replacement():
    service = MemoryService()
    user_id = uuid4()
    old_memory = Mock(spec=Memory)
    old_memory.id = uuid4()
    old_memory.user_id = user_id
    old_memory.status = "active"
    old_memory.memory_type = "preference"

    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[old_memory, None])
    session.add = Mock()
    session.flush = AsyncMock()

    replacement = await service.update_memory(
        session,
        user_id=user_id,
        memory_id=old_memory.id,
        content="I prefer Java",
        confidence=0.8,
        evidence_text="User corrected their preference",
    )

    assert replacement.content == "I prefer Java"
    assert replacement.normalized_content == "i prefer java"
    assert replacement.memory_type == "preference"
    assert replacement.supersedes_id == old_memory.id
    assert old_memory.status == "superseded"
    assert session.add.call_count == 2
    assert session.flush.await_count == 2


@pytest.mark.asyncio
async def test_update_memory_rejects_missing_or_inactive_memory():
    service = MemoryService()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await service.update_memory(
            session, user_id=uuid4(), memory_id=uuid4(), content="New content"
        )

    inactive = Mock(spec=Memory)
    inactive.status = "expired"
    session.scalar.return_value = inactive
    with pytest.raises(ValueError, match="Only active"):
        await service.update_memory(
            session, user_id=uuid4(), memory_id=uuid4(), content="New content"
        )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_memory_rejects_empty_content_without_database_changes():
    service = MemoryService()
    session = AsyncMock()
    session.add = Mock()

    with pytest.raises(ValueError, match="must not be empty"):
        await service.update_memory(
            session, user_id=uuid4(), memory_id=uuid4(), content="  \n"
        )

    session.scalar.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_contradiction_uses_explicit_supersession():
    service = MemoryService()
    user_id = uuid4()
    outdated = Mock(spec=Memory)
    outdated.id = uuid4()
    outdated.user_id = user_id
    outdated.status = "active"
    outdated.memory_type = "fact"
    accepted = Mock(spec=Memory)
    accepted.id = uuid4()
    accepted.user_id = user_id
    accepted.status = "active"
    accepted.memory_type = "fact"
    accepted.supersedes_id = None

    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[outdated, accepted])
    session.flush = AsyncMock()

    result = await service.resolve_contradiction(
        session,
        user_id=user_id,
        outdated_memory_id=outdated.id,
        accepted_memory_id=accepted.id,
    )

    assert result is accepted
    assert outdated.status == "superseded"
    assert accepted.supersedes_id == outdated.id
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_supersede_memory_rejects_self_supersession_without_queries():
    service = MemoryService()
    session = AsyncMock()
    memory_id = uuid4()

    with pytest.raises(ValueError, match="cannot supersede itself"):
        await service.supersede_memory(
            session,
            user_id=uuid4(),
            old_memory_id=memory_id,
            replacement_memory_id=memory_id,
        )

    session.scalar.assert_not_awaited()
    session.flush.assert_not_awaited()
