"""API tests for the search endpoint."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_db
from app.api.v1.search import get_search_service
from app.api.v1.schemas.search import SearchResponse
from app.database.models.user import User
from app.main import app
from app.retrieval.models import RetrievalResult


class FakeSearchService:
    """Fake search service used for API tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def search(
        self,
        session,
        *,
        user_id,
        query: str,
        top_k: int = 5,
        project_id=None,
        document_id=None,
        source_type=None,
    ) -> list[RetrievalResult]:
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "query": query,
                "top_k": top_k,
                "project_id": project_id,
                "document_id": document_id,
                "source_type": source_type,
            }
        )

        return [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="PostgreSQL is used as the primary database.",
                similarity=0.032,
                metadata={"source": "test"},
            ),
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="The application uses pgvector for embeddings.",
                similarity=0.028,
                metadata={"source": "test"},
            ),
        ]


def create_test_user() -> User:
    """Return a deterministic fake user for API tests."""

    return User(
        id=uuid4(),
        email="test@pais.local",
        display_name="PAIS Test User",
    )


def test_search_endpoint_returns_results():
    """POST /api/v1/search should return search results."""

    fake_service = FakeSearchService()
    test_user = create_test_user()

    async def override_search_service():
        return fake_service

    async def override_current_user():
        return test_user

    async def override_db():
        yield object()

    app.dependency_overrides[get_search_service] = override_search_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "What database does the system use?",
                    "top_k": 5,
                },
            )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "What database does the system use?"
        assert len(body["results"]) == 2

        assert body["results"][0]["content"] == (
            "PostgreSQL is used as the primary database."
        )
        assert body["results"][0]["score"] == 0.032

        assert "chunk_id" in body["results"][0]
        assert "document_id" in body["results"][0]

        assert len(fake_service.calls) == 1

        call = fake_service.calls[0]

        assert call["user_id"] == test_user.id
        assert call["query"] == "What database does the system use?"
        assert call["top_k"] == 5

    finally:
        app.dependency_overrides.clear()


def test_search_endpoint_passes_filters():
    """POST /api/v1/search should forward optional filters."""

    fake_service = FakeSearchService()
    test_user = create_test_user()

    project_id = uuid4()
    document_id = uuid4()

    async def override_search_service():
        return fake_service

    async def override_current_user():
        return test_user

    async def override_db():
        yield object()

    app.dependency_overrides[get_search_service] = override_search_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "database",
                    "top_k": 10,
                    "project_id": str(project_id),
                    "document_id": str(document_id),
                    "source_type": "markdown",
                },
            )

        assert response.status_code == 200

        call = fake_service.calls[0]

        assert call["user_id"] == test_user.id
        assert call["query"] == "database"
        assert call["top_k"] == 10
        assert call["project_id"] == project_id
        assert call["document_id"] == document_id
        assert call["source_type"] == "markdown"

    finally:
        app.dependency_overrides.clear()


def test_search_endpoint_rejects_empty_query():
    """POST /api/v1/search should reject an empty query."""

    fake_service = FakeSearchService()

    async def override_search_service():
        return fake_service

    async def override_current_user():
        return create_test_user()

    async def override_db():
        yield object()

    app.dependency_overrides[get_search_service] = override_search_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "",
                    "top_k": 5,
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()


def test_search_endpoint_rejects_invalid_top_k():
    """POST /api/v1/search should reject an invalid top_k."""

    fake_service = FakeSearchService()

    async def override_search_service():
        return fake_service

    async def override_current_user():
        return create_test_user()

    async def override_db():
        yield object()

    app.dependency_overrides[get_search_service] = override_search_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "database",
                    "top_k": 0,
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()


def test_search_endpoint_rejects_whitespace_query():
    """POST /api/v1/search should reject whitespace-only queries."""

    fake_service = FakeSearchService()

    async def override_search_service():
        return fake_service

    async def override_current_user():
        return create_test_user()

    async def override_db():
        yield object()

    app.dependency_overrides[get_search_service] = override_search_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "   ",
                    "top_k": 5,
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()