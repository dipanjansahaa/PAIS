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
        yield client

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