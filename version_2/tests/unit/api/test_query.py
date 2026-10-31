"""API tests for the query endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.api.dependencies import get_current_user, get_db
from app.api.v1.query import get_query_service
from app.database.models.user import User
from app.main import app
from app.query.context import ContextChunk, ContextSource
from app.query.models import QueryMemory, QueryMemorySource, QueryResult
from app.query.relationship_context import (
    QueryRelationship,
    QueryRelationshipSource,
)
from app.query.service import QueryEntityNotFoundError
from fastapi.testclient import TestClient


class FakeQueryService:
    """Fake QueryService used for API tests."""

    def __init__(
        self,
        result: QueryResult,
        error: ValueError | None = None,
    ) -> None:
        self.result = result
        self.error = error
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
        as_of=None,
        entity_type=None,
        entity_id=None,
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
                "as_of": as_of,
                "entity_type": entity_type,
                "entity_id": entity_id,
            }
        )

        if self.error is not None:
            raise self.error
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
        assert body["answer"] == ("PAIS uses PostgreSQL with pgvector. [S1-C1]")

        assert body["model"] == "test-model"
        assert body["latency_ms"] == 125.0
        assert body["truncated"] is False

        assert len(body["sources"]) == 1

        source = body["sources"][0]

        assert source["citation_id"] == "S1"
        assert len(source["chunks"]) == 1

        chunk = source["chunks"][0]

        assert chunk["citation_id"] == "S1-C1"
        assert chunk["content"] == ("PAIS uses PostgreSQL with pgvector.")
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
        assert call["as_of"] is None
        assert call["entity_type"] is None
        assert call["entity_id"] is None

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


def test_query_endpoint_forwards_options_and_relationships():
    """The API should expose relationship evidence and forward valid-time options."""

    source_id = uuid4()
    target_id = uuid4()
    relationship_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    relationship = QueryRelationship(
        citation_id="R1",
        relationship_id=str(relationship_id),
        source_type="project",
        source_id=str(source_id),
        source_label="PAIS",
        relationship_type="depends_on",
        target_type="task",
        target_id=str(target_id),
        target_label="Historical retrieval",
        valid_from=datetime(2025, 1, 1, tzinfo=UTC),
        valid_until=None,
        sources=(
            QueryRelationshipSource(
                citation_id="R1-C1",
                chunk_id=str(chunk_id),
                document_id=str(document_id),
                document_title="Roadmap",
                content="Historical retrieval is a planned milestone.",
            ),
        ),
    )
    result = create_query_result()
    result = QueryResult(
        query=result.query,
        answer=result.answer,
        sources=result.sources,
        model=result.model,
        latency_ms=result.latency_ms,
        truncated=result.truncated,
        memories=result.memories,
        relationships=(relationship,),
    )
    fake_service = FakeQueryService(result=result)
    test_user = create_test_user()
    as_of = "2025-03-01T12:00:00Z"
    configure_dependencies(fake_service, test_user)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "What did PAIS depend on?",
                    "as_of": as_of,
                    "entity_type": "project",
                    "entity_id": str(source_id),
                },
            )

        assert response.status_code == 200
        call = fake_service.calls[0]
        assert call["as_of"] == datetime(2025, 3, 1, 12, tzinfo=UTC)
        assert call["entity_type"] == "project"
        assert call["entity_id"] == source_id

        body = response.json()
        assert body["relationships"] == [
            {
                "citation_id": "R1",
                "relationship_id": str(relationship_id),
                "source_type": "project",
                "source_id": str(source_id),
                "source_label": "PAIS",
                "relationship_type": "depends_on",
                "target_type": "task",
                "target_id": str(target_id),
                "target_label": "Historical retrieval",
                "valid_from": "2025-01-01T00:00:00Z",
                "valid_until": None,
                "sources": [
                    {
                        "citation_id": "R1-C1",
                        "chunk_id": str(chunk_id),
                        "document_id": str(document_id),
                        "document_title": "Roadmap",
                        "content": "Historical retrieval is a planned milestone.",
                    }
                ],
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_rejects_timezone_naive_as_of():
    """Historical timestamps must identify an unambiguous instant."""

    fake_service = FakeQueryService(result=create_query_result())
    configure_dependencies(fake_service, create_test_user())

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "historical question",
                    "as_of": "2025-03-01T12:00:00",
                },
            )
        assert response.status_code == 422
        assert fake_service.calls == []
    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_requires_complete_entity_reference():
    """The API must not infer an entity ID or type when only one is provided."""

    fake_service = FakeQueryService(result=create_query_result())
    configure_dependencies(fake_service, create_test_user())

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={"query": "What is connected?", "entity_type": "project"},
            )
        assert response.status_code == 422
        assert fake_service.calls == []
    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_hides_foreign_or_missing_entity_details():
    """A seed entity unavailable to this user produces a non-disclosing 404."""

    fake_service = FakeQueryService(
        result=create_query_result(),
        error=QueryEntityNotFoundError("Entity does not exist or does not belong to the user."),
    )
    configure_dependencies(fake_service, create_test_user())

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "What is connected?",
                    "entity_type": "project",
                    "entity_id": str(uuid4()),
                },
            )
        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Entity does not exist or does not belong to the authenticated user."
        )
    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_exposes_memory_validity_metadata():
    """Memory responses expose lifecycle and known validity boundaries."""
    memory_id = uuid4()
    valid_from = datetime(2025, 1, 1, tzinfo=UTC)
    memory = QueryMemory(
        citation_id="M1",
        memory_id=str(memory_id),
        memory_type="preference",
        content="I preferred Python for backend work.",
        status="superseded",
        valid_from=valid_from,
        valid_until=None,
        confidence=0.9,
        sources=(
            QueryMemorySource(
                source_kind="manual",
                document_id=None,
                chunk_id=None,
                source_reference="user statement",
                evidence_text="I prefer Python.",
            ),
        ),
    )
    base = create_query_result()
    result = QueryResult(
        query=base.query,
        answer=base.answer,
        sources=base.sources,
        model=base.model,
        latency_ms=base.latency_ms,
        truncated=base.truncated,
        memories=(memory,),
    )
    fake_service = FakeQueryService(result=result)
    configure_dependencies(fake_service, create_test_user())

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={"query": "What was my preference?"},
            )

        assert response.status_code == 200
        memory_body = response.json()["memories"][0]
        assert memory_body["memory_id"] == str(memory_id)
        assert memory_body["status"] == "superseded"
        assert memory_body["valid_from"] == "2025-01-01T00:00:00Z"
        assert memory_body["valid_until"] is None
        assert memory_body["sources"][0]["source_reference"] == "user statement"
    finally:
        app.dependency_overrides.clear()
