"""Integration tests for authenticated memory management endpoints."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from app.api.dependencies import get_current_user, get_db
from app.database.models.memory import Memory, MemorySource
from app.database.models.user import User
from app.main import app
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def memory_api_client(db_session: AsyncSession):
    """Create an authenticated client with two isolated users."""

    user = User(
        email=f"memory-api-{uuid4()}@example.com",
        display_name="Memory API User",
    )
    other_user = User(
        email=f"memory-api-other-{uuid4()}@example.com",
        display_name="Other Memory User",
    )

    db_session.add_all([user, other_user])
    await db_session.flush()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, user, other_user

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_memories_only_returns_current_users_records(
    memory_api_client,
    db_session,
):
    client, user, other_user = memory_api_client

    own = Memory(
        user_id=user.id,
        memory_type="preference",
        content="Prefers concise answers",
        normalized_content="prefers concise answers",
    )
    foreign = Memory(
        user_id=other_user.id,
        memory_type="fact",
        content="Private fact",
        normalized_content="private fact",
    )

    db_session.add_all([own, foreign])
    await db_session.flush()

    db_session.add(
        MemorySource(
            memory_id=own.id,
            source_kind="manual",
            evidence_text="User stated this.",
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/memories")

    assert response.status_code == 200

    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(own.id)]
    assert body["items"][0]["sources"][0]["evidence_text"] == (
        "User stated this."
    )


@pytest.mark.asyncio
async def test_get_memory_hides_other_users_memory(
    memory_api_client,
    db_session,
):
    client, _user, other_user = memory_api_client

    foreign = Memory(
        user_id=other_user.id,
        memory_type="fact",
        content="Private fact",
        normalized_content="private fact",
    )

    db_session.add(foreign)
    await db_session.flush()

    response = await client.get(f"/api/v1/memories/{foreign.id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_correct_memory_creates_replacement_and_retains_history(
    memory_api_client,
    db_session,
):
    client, user, _other_user = memory_api_client

    original = Memory(
        user_id=user.id,
        memory_type="preference",
        content="Prefers long answers",
        normalized_content="prefers long answers",
    )

    db_session.add(original)
    await db_session.flush()

    response = await client.patch(
        f"/api/v1/memories/{original.id}",
        json={
            "content": "Prefers concise answers",
            "confidence": 0.9,
        },
    )

    assert response.status_code == 200, response.text

    replacement = response.json()

    assert replacement["content"] == "Prefers concise answers"
    assert replacement["supersedes_id"] == str(original.id)

    await db_session.refresh(original)
    assert original.status == "superseded"


@pytest.mark.asyncio
async def test_correct_memory_rejects_other_users_memory(
    memory_api_client,
    db_session,
):
    client, _user, other_user = memory_api_client

    foreign = Memory(
        user_id=other_user.id,
        memory_type="fact",
        content="Private fact",
        normalized_content="private fact",
    )

    db_session.add(foreign)
    await db_session.flush()

    response = await client.patch(
        f"/api/v1/memories/{foreign.id}",
        json={"content": "Attempted change"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_memory_removes_owned_memory_and_provenance(
    memory_api_client,
    db_session,
):
    client, user, _other_user = memory_api_client

    memory = Memory(
        user_id=user.id,
        memory_type="fact",
        content="A removable fact",
        normalized_content="a removable fact",
    )

    db_session.add(memory)
    await db_session.flush()

    db_session.add(
        MemorySource(
            memory_id=memory.id,
            source_kind="manual",
        )
    )
    await db_session.flush()

    response = await client.delete(f"/api/v1/memories/{memory.id}")

    assert response.status_code == 204
    assert await db_session.get(Memory, memory.id) is None


@pytest.mark.asyncio
async def test_delete_memory_hides_other_users_memory(
    memory_api_client,
    db_session,
):
    client, _user, other_user = memory_api_client

    foreign = Memory(
        user_id=other_user.id,
        memory_type="fact",
        content="Private fact",
        normalized_content="private fact",
    )

    db_session.add(foreign)
    await db_session.flush()

    response = await client.delete(f"/api/v1/memories/{foreign.id}")

    assert response.status_code == 404
    assert await db_session.get(Memory, foreign.id) is not None


@pytest.mark.asyncio
async def test_memory_endpoints_require_authentication():
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/memories")

    assert response.status_code == 401