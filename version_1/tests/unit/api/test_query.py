"""API tests for the query endpoint."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_db
from app.api.v1.query import get_query_service
from app.database.models.user import User
from app.main import app
from app.query.context import ContextChunk, ContextSource
from app.query.models import QueryResult


class FakeQueryService:
    """Fake QueryService used for API tests."""

    def __init__(
        self,
        result: QueryResult,
    ) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def query(
        self,
        session,
        *,
        user_id,
        query: str,
        top_k: int = 5,
        project_id=None,
        document_id=None,
        source_type=None,
        temperature: float = 0.0,
    ) -> QueryResult:
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "query": query,
                "top_k": top_k,
                "project_id": project_id,
                "document_id": document_id,
                "source_type": source_type,
                "temperature": temperature,
            }
        )

        return self.result


def create_test_user() -> User:
    """Return a deterministic fake user for API tests."""

    return User(
        id=uuid4(),
        email="query-test@pais.local",
        display_name="PAIS Query Test User",
    )


def create_query_result() -> QueryResult:
    """Create a representative grounded query result."""

    document_id = uuid4()
    chunk_id = uuid4()

    chunk = ContextChunk(
        citation_id="S1-C1",
        chunk_id=str(chunk_id),
        document_id=str(document_id),
        content="PAIS uses PostgreSQL with pgvector.",
        similarity=0.91,
        metadata={"source": "architecture.md"},
    )

    source = ContextSource(
        citation_id="S1",
        document_id=str(document_id),
        chunks=(chunk,),
    )

    return QueryResult(
        query="What database does PAIS use?",
        answer="PAIS uses PostgreSQL with pgvector. [S1-C1]",
        sources=(source,),
        model="test-model",
        latency_ms=125.0,
        truncated=False,
    )


def configure_dependencies(
    query_service: FakeQueryService,
    test_user: User,
) -> None:
    """Configure FastAPI dependency overrides for API tests."""

    async def override_query_service():
        return query_service

    async def override_current_user():
        return test_user

    async def override_db():
        yield object()

    app.dependency_overrides[get_query_service] = override_query_service
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db


def test_query_endpoint_returns_grounded_response():
    """POST /api/v1/query should return the grounded query result."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "What database does PAIS use?",
                    "top_k": 5,
                },
            )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "What database does PAIS use?"
        assert body["answer"] == (
            "PAIS uses PostgreSQL with pgvector. [S1-C1]"
        )

        assert body["model"] == "test-model"
        assert body["latency_ms"] == 125.0
        assert body["truncated"] is False

        assert len(body["sources"]) == 1

        source = body["sources"][0]

        assert source["citation_id"] == "S1"
        assert len(source["chunks"]) == 1

        chunk = source["chunks"][0]

        assert chunk["citation_id"] == "S1-C1"
        assert chunk["content"] == (
            "PAIS uses PostgreSQL with pgvector."
        )
        assert chunk["score"] == 0.91
        assert chunk["metadata"] == {
            "source": "architecture.md",
        }

        assert len(fake_service.calls) == 1

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_passes_filters_and_temperature():
    """POST /api/v1/query should forward query options."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    project_id = uuid4()
    document_id = uuid4()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "database architecture",
                    "top_k": 10,
                    "project_id": str(project_id),
                    "document_id": str(document_id),
                    "source_type": "markdown",
                    "temperature": 0.2,
                },
            )

        assert response.status_code == 200

        assert len(fake_service.calls) == 1

        call = fake_service.calls[0]

        assert call["user_id"] == test_user.id
        assert call["query"] == "database architecture"
        assert call["top_k"] == 10
        assert call["project_id"] == project_id
        assert call["document_id"] == document_id
        assert call["source_type"] == "markdown"
        assert call["temperature"] == 0.2

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_uses_default_values():
    """POST /api/v1/query should use the documented defaults."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "database",
                },
            )

        assert response.status_code == 200

        call = fake_service.calls[0]

        assert call["top_k"] == 5
        assert call["project_id"] is None
        assert call["document_id"] is None
        assert call["source_type"] is None
        assert call["temperature"] == 0.0

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_rejects_empty_query():
    """POST /api/v1/query should reject an empty query."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "",
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_rejects_whitespace_query():
    """POST /api/v1/query should reject whitespace-only queries."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "   ",
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_rejects_invalid_top_k():
    """POST /api/v1/query should reject invalid top_k."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "database",
                    "top_k": 0,
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_rejects_invalid_temperature():
    """POST /api/v1/query should reject an invalid temperature."""

    fake_service = FakeQueryService(
        result=create_query_result(),
    )
    test_user = create_test_user()

    configure_dependencies(
        query_service=fake_service,
        test_user=test_user,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "database",
                    "temperature": -0.1,
                },
            )

        assert response.status_code == 422
        assert fake_service.calls == []

    finally:
        app.dependency_overrides.clear()