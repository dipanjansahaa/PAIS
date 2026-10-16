from __future__ import annotations

from io import BytesIO

import pytest
from sqlalchemy import select

from app.api.v1.search import get_search_service
from app.api.v1.query import get_query_service
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.llm.models import LLMResponse
from app.main import app
from app.query.context import ContextBuilder
from app.query.service import QueryService


class FakeE2EQueryLLM:
    """Deterministic LLM used for the document-to-query E2E workflow."""

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
        assert "SOURCES:" in user_message.content
        assert "QUESTION:" in user_message.content

        assert "PostgreSQL" in user_message.content
        assert "pgvector" in user_message.content

        return LLMResponse(
            content=(
                "PAIS uses PostgreSQL with pgvector for "
                "document retrieval. [S1-C1]"
            ),
            model="e2e-test-model",
            usage=None,
            latency_ms=1.0,
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_document_upload_to_grounded_query_end_to_end(
    e2e_api_client,
    db_session,
):
    """
    Verify the complete document-to-grounded-query workflow.

    The document is uploaded through the public API and then queried
    through the public query API without manually creating database
    documents or chunks.
    """

    client, test_user = e2e_api_client

    content = (
        b"# PAIS Architecture\n\n"
        b"PAIS uses PostgreSQL with pgvector for persistent storage "
        b"and semantic document retrieval.\n\n"
        b"The retrieval layer combines vector search and lexical search."
    )

    upload_response = await client.post(
        "/api/v1/documents",
        files={
            "file": (
                "pais-architecture.md",
                BytesIO(content),
                "text/markdown",
            )
        },
        data={
            "title": "PAIS Architecture",
            "source_type": "markdown",
        },
    )

    assert upload_response.status_code == 201

    uploaded_document = upload_response.json()
    document_id = uploaded_document["id"]

    document = await db_session.get(
        Document,
        document_id,
    )

    assert document is not None
    assert document.user_id == test_user.id

    chunks = list(
        (
            await db_session.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document.id,
                )
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()
    )

    assert chunks

    fake_llm = FakeE2EQueryLLM()

    search_service = app.dependency_overrides[
        get_search_service
    ]()

    query_service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=fake_llm,
    )

    def override_get_query_service():
        return query_service

    app.dependency_overrides[get_query_service] = (
        override_get_query_service
    )

    try:
        query_response = await client.post(
            "/api/v1/query",
            json={
                "query": "What database does PAIS use?",
                "top_k": 5,
                "temperature": 0.0,
            },
        )

        assert query_response.status_code == 200

        data = query_response.json()

        assert data["query"] == "What database does PAIS use?"

        assert data["answer"] == (
            "PAIS uses PostgreSQL with pgvector for "
            "document retrieval. [S1-C1]"
        )

        assert data["model"] == "e2e-test-model"
        assert data["latency_ms"] == 1.0
        assert data["truncated"] is False

        assert data["sources"]

        source = data["sources"][0]

        assert source["citation_id"] == "S1"
        assert source["document_id"] == document_id

        assert source["chunks"]

        result_chunk = source["chunks"][0]

        assert result_chunk["citation_id"] == "S1-C1"
        assert result_chunk["document_id"] == document_id
        assert result_chunk["chunk_id"]

        assert "PostgreSQL" in result_chunk["content"]
        assert "pgvector" in result_chunk["content"]

        assert len(fake_llm.messages) == 1

        generation_prompt = fake_llm.messages[0][-1].content

        assert "SOURCES:" in generation_prompt
        assert "QUESTION:" in generation_prompt
        assert "PostgreSQL" in generation_prompt
        assert "pgvector" in generation_prompt
        assert "S1-C1" in generation_prompt
        assert "What database does PAIS use?" in generation_prompt

    finally:
        app.dependency_overrides.pop(
            get_query_service,
            None,
        )