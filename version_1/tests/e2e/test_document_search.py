from __future__ import annotations

from io import BytesIO

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk


@pytest.mark.asyncio
async def test_document_upload_is_searchable_end_to_end(
    e2e_api_client,
    db_session: AsyncSession,
):
    """
    Verify the complete document-to-search workflow.

    The test starts at the document upload API and verifies that the
    uploaded document becomes searchable through the search API.
    """

    client, test_user = e2e_api_client

    content = (
        b"# PAIS Architecture Notes\n\n"
        b"PAIS uses PostgreSQL with pgvector for semantic document retrieval.\n\n"
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
            "title": "PAIS Architecture Notes",
            "source_type": "markdown",
        },
    )

    assert upload_response.status_code == 201

    uploaded_document = upload_response.json()

    document_id = uploaded_document["id"]

    assert document_id
    assert uploaded_document["title"] == "PAIS Architecture Notes"
    assert uploaded_document["source_type"] == "markdown"
    assert uploaded_document["file_name"] == "pais-architecture.md"
    assert uploaded_document["mime_type"] == "text/markdown"

    document = await db_session.scalar(
        select(Document).where(
            Document.id == document_id,
        )
    )

    assert document is not None
    assert document.user_id == test_user.id
    assert document.title == "PAIS Architecture Notes"
    assert document.raw_text == content.decode("utf-8")

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
    assert [chunk.chunk_index for chunk in chunks] == list(
        range(len(chunks))
    )

    assert all(
        chunk.embedding is not None
        for chunk in chunks
    )

    assert all(
        len(chunk.embedding) == 384
        for chunk in chunks
        if chunk.embedding is not None
    )

    search_response = await client.post(
        "/api/v1/search",
        json={
            "query": "PostgreSQL pgvector semantic document retrieval",
            "top_k": 5,
        },
    )

    assert search_response.status_code == 200

    search_data = search_response.json()

    assert (
        search_data["query"]
        == "PostgreSQL pgvector semantic document retrieval"
    )

    assert search_data["results"]

    result_document_ids = {
        result["document_id"]
        for result in search_data["results"]
    }

    assert document_id in result_document_ids

    matching_results = [
        result
        for result in search_data["results"]
        if result["document_id"] == document_id
    ]

    assert matching_results

    assert any(
        "PostgreSQL" in result["content"]
        and "pgvector" in result["content"]
        for result in matching_results
    )

    assert all(
        result["chunk_id"]
        for result in matching_results
    )

    assert all(
        result["score"] > 0
        for result in matching_results
    )