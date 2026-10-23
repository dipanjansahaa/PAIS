from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.database.models.user import User
from app.main import app

from unittest.mock import AsyncMock

from app.api.v1.documents import get_intelligence_workflow_service
from app.intelligence.persistence_service import IntelligencePersistenceResult

from sqlalchemy import select

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.api.v1.documents import get_intelligence_workflow_service


@pytest_asyncio.fixture
async def override_intelligence_workflow():
    workflow = AsyncMock()
    workflow.extract_and_persist.return_value = (
        IntelligencePersistenceResult()
    )
    return workflow


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession):
    """
    Create an isolated API test client using the test database session.
    """

    test_user = User(
        email=f"api-test-{uuid4()}@example.com",
        display_name="API Test User",
    )

    db_session.add(test_user)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[
        get_intelligence_workflow_service
    ] = override_intelligence_workflow

    transport = ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()

        # Clean up data created during the test.
        await db_session.delete(test_user)
        await db_session.commit()


@pytest.mark.asyncio
async def test_create_document_successfully(
    api_client: httpx.AsyncClient,
):
    response = await api_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "project-notes.md",
                BytesIO(
                    b"# Project Notes\n\n"
                    b"This is a project document.\n\n"
                    b"PostgreSQL is used as the database."
                ),
                "text/markdown",
            )
        },
        data={
            "title": "Project Notes",
            "source_type": "markdown",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"]
    assert data["title"] == "Project Notes"
    assert data["source_type"] == "markdown"
    assert data["file_name"] == "project-notes.md"
    assert data["mime_type"] == "text/markdown"
    assert data["project_id"] is None


@pytest.mark.asyncio
async def test_create_duplicate_document_returns_conflict(
    api_client: httpx.AsyncClient,
):
    content = (
        b"# Duplicate Notes\n\n"
        b"This document should only be ingested once."
    )

    first_response = await api_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "duplicate-notes.md",
                BytesIO(content),
                "text/markdown",
            )
        },
        data={
            "title": "Duplicate Notes",
            "source_type": "markdown",
        },
    )

    assert first_response.status_code == 201

    second_response = await api_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "duplicate-notes-copy.md",
                BytesIO(content),
                "text/markdown",
            )
        },
        data={
            "title": "Duplicate Notes Copy",
            "source_type": "markdown",
        },
    )

    assert second_response.status_code == 409

    response_data = second_response.json()

    assert "detail" in response_data
    assert "Document already exists" in response_data["detail"]


@pytest.mark.asyncio
async def test_create_document_rejects_oversized_upload(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)

    response = await api_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "large.txt",
                BytesIO(b"01234567890"),
                "text/plain",
            )
        },
        data={
            "title": "Large Document",
            "source_type": "text",
        },
    )

    assert response.status_code == 413

    response_data = response.json()

    assert "detail" in response_data
    assert "maximum allowed size" in response_data["detail"]


@pytest.mark.asyncio
async def test_create_document_accepts_upload_at_size_limit(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)

    response = await api_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "small.txt",
                BytesIO(b"0123456789"),
                "text/plain",
            )
        },
        data={
            "title": "Small Document",
            "source_type": "text",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def override_intelligence_workflow():
    workflow = AsyncMock()
    workflow.extract_and_persist.return_value = (
        IntelligencePersistenceResult()
    )
    return workflow


app.dependency_overrides[
    get_intelligence_workflow_service
] = override_intelligence_workflow


@pytest.mark.asyncio
async def test_upload_rolls_back_when_intelligence_extraction_fails(
    api_client,
    db_session,
):
    """A failed extraction must not leave an uploaded document behind."""

    unique_marker = uuid4().hex
    filename = f"rollback-test-{unique_marker}.txt"
    title = f"Rollback Test {unique_marker}"
    content = f"Review the deployment plan. Test marker: {unique_marker}"

    failing_workflow = AsyncMock()
    failing_workflow.extract_and_persist.side_effect = RuntimeError(
        "Simulated extraction failure"
    )

    # Override the workflow specifically for this test.
    app.dependency_overrides[
        get_intelligence_workflow_service
    ] = lambda: failing_workflow

    try:
        response = await api_client.post(
            "/api/v1/documents",
            data={
                "title": title,
                "source_type": "notes",
            },
            files={
                "file": (
                    filename,
                    content.encode("utf-8"),
                    "text/plain",
                )
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_intelligence_workflow_service,
            None,
        )

    assert response.status_code == 502, response.text
    assert "upload was rolled back" in response.json()["detail"].lower()

    document = await db_session.scalar(
        select(Document).where(Document.file_name == filename)
    )
    assert document is None

    chunks = await db_session.scalars(
        select(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.file_name == filename)
    )
    assert list(chunks.all()) == []