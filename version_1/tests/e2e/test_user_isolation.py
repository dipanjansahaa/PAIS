"""End-to-end tests for cross-user data isolation."""

from __future__ import annotations

from dataclasses import dataclass

from httpx import AsyncClient
from sqlalchemy import select
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.api.v1.query import get_query_service
from app.api.v1.search import get_search_service
from app.database.models.user import User
from app.database.session import get_db
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.main import app
from app.query.context import ContextBuilder
from app.query.service import QueryService


@dataclass
class FakeIsolationQueryLLM:
    """Deterministic LLM used to verify query-level isolation."""

    def __init__(self) -> None:
        self.messages = []

    async def generate(
        self,
        messages,
        *,
        temperature: float = 0.0,
        response_schema=None,
    ) -> LLMResponse:
        self.messages.append(messages)

        user_message = messages[-1]

        assert user_message.role == "user"

        return LLMResponse(
            content=(
                "The retrieved information confirms the requested fact. "
                "[S1-C1]"
            ),
            model="e2e-isolation-model",
            usage=None,
            latency_ms=1.0,
            finish_reason="stop",
        )


async def test_users_cannot_retrieve_each_others_documents(
    e2e_api_client,
    db_session,
):
    """Verify document ingestion, search, and query remain user-isolated."""

    client, user_a = e2e_api_client

    # ------------------------------------------------------------------
    # Create User B.
    # ------------------------------------------------------------------
    user_b = User(
        email=f"e2e-user-b-{uuid4()}@pais.local",
        display_name="E2E User B",
    )
    db_session.add(user_b)
    await db_session.flush()

    # ------------------------------------------------------------------
    # User A uploads a document containing A-only information.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_a

    response_a_upload = await client.post(
        "/api/v1/documents",
        files={
            "file": (
                "user-a.md",
                (
                    b"# User A Knowledge\n\n"
                    b"PROJECT-A-SECRET contains the PostgreSQL migration "
                    b"details owned exclusively by User A."
                ),
                "text/markdown",
            ),
        },
        data={
            "title": "User A Knowledge",
            "source_type": "e2e",
        },
    )

    assert response_a_upload.status_code == 201

    document_a = response_a_upload.json()
    document_a_id = document_a["id"]

    # ------------------------------------------------------------------
    # User B uploads a separate document containing B-only information.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_b

    response_b_upload = await client.post(
        "/api/v1/documents",
        files={
            "file": (
                "user-b.md",
                (
                    b"# User B Knowledge\n\n"
                    b"PROJECT-B-SECRET contains the Redis deployment "
                    b"details owned exclusively by User B."
                ),
                "text/markdown",
            ),
        },
        data={
            "title": "User B Knowledge",
            "source_type": "e2e",
        },
    )

    assert response_b_upload.status_code == 201

    document_b = response_b_upload.json()
    document_b_id = document_b["id"]

    assert document_a_id != document_b_id

    # ------------------------------------------------------------------
    # User A can search for User A's document.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_a

    response_a_search = await client.post(
        "/api/v1/search",
        json={
            "query": "What does PROJECT-A-SECRET contain?",
            "top_k": 5,
            "temperature": 0.0,
        },
    )

    assert response_a_search.status_code == 200

    search_a = response_a_search.json()

    assert search_a["results"]
    assert any(
        result["document_id"] == document_a_id
        for result in search_a["results"]
    )
    assert all(
        result["document_id"] != document_b_id
        for result in search_a["results"]
    )

    # ------------------------------------------------------------------
    # User B can search for User B's document but not User A's.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_b

    response_b_search = await client.post(
        "/api/v1/search",
        json={
            "query": "What does PROJECT-A-SECRET contain?",
            "top_k": 5,
            "temperature": 0.0,
        },
    )

    assert response_b_search.status_code == 200

    search_b = response_b_search.json()

    assert search_b["results"]
    assert any(
        result["document_id"] == document_b_id
        for result in search_b["results"]
    )
    assert all(
        result["document_id"] != document_a_id
        for result in search_b["results"]
    )

    # ------------------------------------------------------------------
    # User B searches specifically for User A's unique information.
    #
    # This is the stronger isolation assertion: even when the query
    # explicitly asks for A's content, A's document must not appear.
    # ------------------------------------------------------------------
    response_b_cross_search = await client.post(
        "/api/v1/search",
        json={
            "query": "PROJECT-A-SECRET PostgreSQL migration",
            "top_k": 5,
        },
    )

    assert response_b_cross_search.status_code == 200

    cross_search = response_b_cross_search.json()

    assert all(
        result["document_id"] != document_a_id
        for result in cross_search["results"]
    )

    # ------------------------------------------------------------------
    # Configure a deterministic QueryService for the public /query path.
    # ------------------------------------------------------------------
    fake_llm = FakeIsolationQueryLLM()

    search_service = app.dependency_overrides[get_search_service]()

    app.dependency_overrides[get_query_service] = lambda: QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=fake_llm,
    )

    # ------------------------------------------------------------------
    # User A can query information from User A's document.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_a

    response_a_query = await client.post(
        "/api/v1/query",
        json={
            "query": "What does PROJECT-A-SECRET contain?",
            "top_k": 5,
            "temperature": 0.0,
        },
    )

    assert response_a_query.status_code == 200

    query_a = response_a_query.json()

    assert query_a["answer"]
    assert query_a["sources"]
    assert any(
        source["document_id"] == document_a_id
        for source in query_a["sources"]
    )

    # ------------------------------------------------------------------
    # User B queries for User A's information.
    #
    # The query may still produce a deterministic LLM response, but the
    # important invariant is that User A's source must not enter the
    # grounded context.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_b

    response_b_cross_query = await client.post(
        "/api/v1/query",
        json={
            "query": "What does PROJECT-A-SECRET contain?",
            "top_k": 5,
            "temperature": 0.0,
        },
    )

    assert response_b_cross_query.status_code == 200

    query_b_cross = response_b_cross_query.json()

    assert all(
        source["document_id"] != document_a_id
        for source in query_b_cross["sources"]
    )

    if fake_llm.messages:
        final_user_message = fake_llm.messages[-1][-1]

        assert final_user_message.role == "user"

        prompt = final_user_message.content

        sources_section, question_section = prompt.split(
            "QUESTION:",
            maxsplit=1,
        )

        assert "PROJECT-A-SECRET" not in sources_section
        assert "User A Knowledge" not in sources_section
        assert "User B Knowledge" in sources_section

        assert "PROJECT-A-SECRET" in question_section

    # ------------------------------------------------------------------
    # Restore the normal E2E overrides before cleanup.
    # ------------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: user_a

    await db_session.delete(user_b)
    await db_session.flush()