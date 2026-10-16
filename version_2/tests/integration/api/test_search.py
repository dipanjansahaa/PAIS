from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.project import Project
from app.database.models.user import User
from app.main import app


@pytest_asyncio.fixture
async def search_api_client(db_session: AsyncSession):
    """
    Create an isolated API test client using the test database session.
    """

    test_user = User(
        email=f"search-test-{uuid4()}@example.com",
        display_name="Search Test User",
    )

    db_session.add(test_user)
    await db_session.flush()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, test_user

    app.dependency_overrides.clear()

    await db_session.delete(test_user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_search_endpoint_returns_real_results(
    search_api_client,
    db_session: AsyncSession,
):
    client, test_user = search_api_client

    document = Document(
        user_id=test_user.id,
        title="Python Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="python-notes.txt",
        content_hash=f"hash-{uuid4()}",
        raw_text="Python is a programming language used for machine learning.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Python is a programming language used for machine learning.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.commit()

    response = await client.post(
        "/api/v1/search",
        json={
            "query": "Python programming language",
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "Python programming language"
    assert len(data["results"]) >= 1

    result = data["results"][0]

    assert result["document_id"] == str(document.id)
    assert result["chunk_id"] == str(chunk.id)
    assert "Python" in result["content"]


@pytest.mark.asyncio
async def test_search_endpoint_isolates_users(
    db_session: AsyncSession,
):
    """
    Verify that search results are restricted to the authenticated user.
    """

    user_a = User(
        email=f"search-user-a-{uuid4()}@example.com",
        display_name="Search User A",
    )
    user_b = User(
        email=f"search-user-b-{uuid4()}@example.com",
        display_name="Search User B",
    )

    db_session.add_all([user_a, user_b])
    await db_session.flush()

    document_a = Document(
        user_id=user_a.id,
        title="User A Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="user-a.txt",
        content_hash=f"hash-a-{uuid4()}",
        raw_text="Python machine learning notes belonging to user A.",
    )

    document_b = Document(
        user_id=user_b.id,
        title="User B Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="user-b.txt",
        content_hash=f"hash-b-{uuid4()}",
        raw_text="Python machine learning notes belonging to user B.",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="Python machine learning notes belonging to user A.",
        embedding=[1.0] + [0.0] * 383,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="Python machine learning notes belonging to user B.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user_a

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "Python machine learning",
                    "top_k": 10,
                },
            )

        assert response.status_code == 200

        data = response.json()

        result_document_ids = {
            result["document_id"]
            for result in data["results"]
        }

        assert str(document_a.id) in result_document_ids
        assert str(document_b.id) not in result_document_ids

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_endpoint_respects_project_filter(
    db_session: AsyncSession,
):
    """
    Verify that the project_id filter restricts search results correctly.
    """

    user = User(
        email=f"project-search-{uuid4()}@example.com",
        display_name="Project Search User",
    )
    db_session.add(user)
    await db_session.flush()

    project_a = Project(
        user_id=user.id,
        name="Project A",
    )

    project_b = Project(
        user_id=user.id,
        name="Project B",
    )

    db_session.add_all([project_a, project_b])
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        project_id=project_a.id,
        title="Project A Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="project-a.txt",
        content_hash=f"hash-a-{uuid4()}",
        raw_text="Machine learning architecture for Project A.",
    )

    document_b = Document(
        user_id=user.id,
        project_id=project_b.id,
        title="Project B Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="project-b.txt",
        content_hash=f"hash-b-{uuid4()}",
        raw_text="Machine learning architecture for Project B.",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="Machine learning architecture for Project A.",
        embedding=[1.0] + [0.0] * 383,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="Machine learning architecture for Project B.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "machine learning architecture",
                    "top_k": 10,
                    "project_id": str(project_a.id),
                },
            )

        assert response.status_code == 200

        data = response.json()

        result_document_ids = {
            result["document_id"]
            for result in data["results"]
        }

        assert str(document_a.id) in result_document_ids
        assert str(document_b.id) not in result_document_ids

    finally:
        app.dependency_overrides.clear()